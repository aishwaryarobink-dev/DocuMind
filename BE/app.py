try:
    __import__("pysqlite3")
    import sys

    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except Exception:
    pass

import io
import json
import os
import uuid
import hashlib
from pathlib import Path
import threading
import pypdf
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.url_map.strict_slashes = False
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

CORS(
    app,
    resources={
        r"/*": {
            "origins": [
                "http://localhost:5173",
                "http://localhost:5174",
                "https://documind-clinical-ai.vercel.app",
            ],
            "methods": ["GET", "POST", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
        }
    },
)

CHROMA_PATH = os.environ.get("CHROMA_PATH", "/tmp/chroma_store")
MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
MAX_DISTANCE = float(os.environ.get("MAX_RAG_DISTANCE", "0.8"))
EMBED_BATCH_SIZE = int(os.environ.get("EMBED_BATCH_SIZE", "64"))

_chroma_client = None
_cohere_client = None
_groq_client = None

sessions = {}
upload_locks = {}
upload_locks_guard = threading.Lock()


def get_upload_lock(session_id, doc_id):
    lock_key = f"{session_id}:{doc_id}"

    with upload_locks_guard:
        if lock_key not in upload_locks:
            upload_locks[lock_key] = threading.Lock()

        return upload_locks[lock_key]


def get_chroma_client():
    global _chroma_client

    if _chroma_client is None:
        import chromadb

        Path(CHROMA_PATH).mkdir(parents=True, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)

    return _chroma_client


def get_cohere_client():
    global _cohere_client

    if _cohere_client is None:
        from cohere import ClientV2 as CohereClient

        api_key = os.environ.get("COHERE_API_KEY")
        if not api_key:
            raise RuntimeError("COHERE_API_KEY is not configured")

        _cohere_client = CohereClient(api_key=api_key)

    return _cohere_client


def get_groq_client():
    global _groq_client

    if _groq_client is None:
        from groq import Groq

        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not configured")

        _groq_client = Groq(api_key=api_key)

    return _groq_client


def extract_embeddings(response):
    if hasattr(response.embeddings, "float_"):
        return response.embeddings.float_

    if hasattr(response.embeddings, "float"):
        return response.embeddings.float

    return response.embeddings


def embed_documents(texts):
    embeddings = []
    cohere_client = get_cohere_client()

    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start : start + EMBED_BATCH_SIZE]
        response = cohere_client.embed(
            texts=batch,
            model="embed-english-light-v3.0",
            input_type="search_document",
            embedding_types=["float"],
        )
        embeddings.extend(extract_embeddings(response))

    return embeddings


def embed_query(text):
    response = get_cohere_client().embed(
        texts=[text],
        model="embed-english-light-v3.0",
        input_type="search_query",
        embedding_types=["float"],
    )

    return extract_embeddings(response)[0]


def get_collection(session_id):
    safe_id = session_id[:36].replace("-", "_")

    return get_chroma_client().get_or_create_collection(
        name=f"session_{safe_id}",
        metadata={"hnsw:space": "cosine"},
    )


def extract_pdf_text(file_bytes):
    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    pages = []

    for i, page in enumerate(reader.pages):
        text = page.extract_text()

        if text and text.strip():
            pages.append({"page": i + 1, "text": text.strip()})

    return pages


def split_into_chunks(pages, chunk_size=900, overlap=120):
    chunks = []

    for page_data in pages:
        text = page_data["text"]
        page_num = page_data["page"]
        start = 0

        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end]

            if chunk_text.strip():
                chunks.append(
                    {
                        "text": chunk_text,
                        "page": page_num,
                        "chunk_index": len(chunks),
                    }
                )

            if end == len(text):
                break

            start = max(end - overlap, start + 1)

    return chunks


def build_citations(metadatas, distances):
    citation_map = {}

    for meta, dist in zip(metadatas, distances):
        if dist > MAX_DISTANCE:
            continue

        filename = meta.get("filename", "document")
        page = meta.get("page", "?")
        citation_map.setdefault(filename, set()).add(page)

    return [
        {"filename": filename, "pages": sorted(list(pages))}
        for filename, pages in citation_map.items()
    ]


def build_rag_messages(question, chunks, metadatas, distances, history):
    context_parts = []

    for chunk, meta, dist in zip(chunks, metadatas, distances):
        if dist > MAX_DISTANCE:
            continue

        source = (
            f"[Source: {meta.get('filename', 'document')}, "
            f"Page {meta.get('page', '?')}]"
        )
        context_parts.append(f"{source}\n{chunk}")

    context = "\n\n---\n\n".join(context_parts)

    if context_parts:
        system_prompt = f"""
You are DocuMind, an intelligent document analysis assistant.

Rules:
1. Answer only using the provided document context
2. Do not hallucinate or use external knowledge
3. If information is unavailable, say:
"I could not find this information in the uploaded documents."
4. Mention source document and page number
5. Keep answers concise and structured

Document Context:
{context}
"""
    else:
        system_prompt = """
You are DocuMind.

No relevant information was found in the uploaded documents.

Reply with:
"I could not find relevant information in the uploaded documents."
"""

    messages = [{"role": "system", "content": system_prompt}]

    for h in history[-8:]:
        role = h.get("role")
        content = h.get("content", "").strip()

        if role in ["user", "assistant"] and content:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": question})
    return messages


@app.route("/")
def home():
    return jsonify(
        {
            "status": "running",
            "service": "DocuMind API",
            "model": MODEL,
        }
    )


@app.route("/api/health", methods=["GET"])
@app.route("/api/health/", methods=["GET"])
def health():
    return jsonify(
        {
            "status": "ok",
            "service": "DocuMind API",
            "model": MODEL,
        }
    )


@app.route("/api/upload", methods=["POST"])
def upload():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["file"]
        session_id = request.form.get("session_id") or str(uuid.uuid4())
        filename = secure_filename(file.filename or "")

        if not filename.lower().endswith(".pdf"):
            return jsonify({"error": "Only PDF files supported"}), 400

        file_bytes = file.read()

        if len(file_bytes) > app.config["MAX_CONTENT_LENGTH"]:
            return jsonify({"error": "File exceeds 10MB limit"}), 400

        doc_id = hashlib.md5(file_bytes).hexdigest()[:12]
        collection = get_collection(session_id)

        with get_upload_lock(session_id, doc_id):
            existing = collection.get(
                where={"doc_id": doc_id},
                include=["metadatas"],
            )

            if existing["ids"]:
                metadatas = existing.get("metadatas") or []
                pages = sorted(
                    {
                        meta.get("page")
                        for meta in metadatas
                        if meta.get("page") is not None
                    }
                )

                return jsonify({
                    "success": False,
                    "duplicate": True,
                    "error": "Document already uploaded",
                    "doc_id": doc_id,
                    "session_id": session_id,
                    "name": file.filename,
                    "pages": len(pages),
                    "chunk_count": len(existing["ids"]),
                }), 409

            pages = extract_pdf_text(file_bytes)

            if not pages:
                return jsonify({
                    "error": "No readable text found in PDF"
                }), 400

            chunks = split_into_chunks(pages)

            embeddings = embed_documents(
                [c["text"] for c in chunks]
            )

            collection.add(
                ids=[
                    f"{doc_id}_{c['chunk_index']}"
                    for c in chunks
                ],
                documents=[
                    c["text"] for c in chunks
                ],
                embeddings=embeddings,
                metadatas=[
                    {
                        "doc_id": doc_id,
                        "page": c["page"],
                        "filename": file.filename,
                    }
                    for c in chunks
                ],
            )

            sessions.setdefault(session_id, {})[doc_id] = {
                "name": filename,
                "pages": len(pages),
                "chunk_count": len(chunks),
            }

            return jsonify(
                {
                    "success": True,
                    "doc_id": doc_id,
                    "session_id": session_id,
                    "name": filename,
                    "pages": len(pages),
                    "chunk_count": len(chunks),
                }
            )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/search", methods=["POST"])
def search():
    try:
        data = request.get_json(silent=True) or {}
        question = data.get("question", "").strip()
        session_id = data.get("session_id", "").strip()

        if not question or not session_id:
            return jsonify({"error": "question and session_id required"}), 400

        collection = get_collection(session_id)

        if collection.count() == 0:
            return jsonify({"error": "No documents found"}), 400

        results = collection.query(
            query_embeddings=[embed_query(question)],
            n_results=min(3, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        formatted = []
        for chunk, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            formatted.append(
                {
                    "text": chunk,
                    "filename": meta.get("filename"),
                    "page": meta.get("page"),
                    "distance": round(dist, 4),
                }
            )

        return jsonify({"results": formatted})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(silent=True) or {}
        question = data.get("question", "").strip()
        session_id = data.get("session_id", "").strip()
        history = data.get("history", [])

        if not question:
            return jsonify({"error": "question required"}), 400

        if not session_id:
            return jsonify({"error": "session_id required"}), 400

        collection = get_collection(session_id)

        if collection.count() == 0:
            return jsonify({"error": "No uploaded documents"}), 400

        results = collection.query(
            query_embeddings=[embed_query(question)],
            n_results=min(3, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        chunks = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]
        citations = build_citations(metadatas, distances)
        messages = build_rag_messages(question, chunks, metadatas, distances, history)

        def generate():
            yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"

            try:
                stream = get_groq_client().chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=1024,
                    stream=True,
                )

                for chunk in stream:
                    text = chunk.choices[0].delta.content

                    if text:
                        yield f"data: {json.dumps({'type': 'text', 'text': text})}\n\n"

            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

            yield "data: [DONE]\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/documents/<session_id>/<doc_id>", methods=["DELETE"])
def delete_document(session_id, doc_id):
    try:
        collection = get_collection(session_id)
        existing = collection.get(where={"doc_id": doc_id})

        if existing["ids"]:
            collection.delete(ids=existing["ids"])

        if session_id in sessions and doc_id in sessions[session_id]:
            del sessions[session_id][doc_id]

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)