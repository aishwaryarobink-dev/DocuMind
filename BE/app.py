__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import os
import io
import json
import uuid
import hashlib
from pathlib import Path
from flask import Flask, request, Response, stream_with_context, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import pypdf
import chromadb
import cohere
from groq import Groq

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {
    "origins": [
        "http://localhost:5173",
        "http://localhost:5174",
        "https://documind-clinical-ai.vercel.app"
    ],
    "methods": ["GET", "POST", "DELETE", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization"],
    "supports_credentials": False
}})

# ── ChromaDB setup ────────────────────────────────────────────────────────────
CHROMA_PATH = "/tmp/chroma_store"
Path(CHROMA_PATH).mkdir(exist_ok=True)
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)

# ── Cohere client (direct API — no chromadb wrapper) ─────────────────────────
cohere_client = cohere.Client(os.environ.get("COHERE_API_KEY", ""))

# ── Groq client ───────────────────────────────────────────────────────────────
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
MODEL = "llama-3.3-70b-versatile"

sessions = {}


# ── Embedding helpers ─────────────────────────────────────────────────────────
def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed a list of document chunks."""
    response = cohere_client.embed(
        texts=texts,
        model="embed-english-light-v3.0",
        input_type="search_document"
    )
    return response.embeddings


def embed_query(text: str) -> list[float]:
    """Embed a single search query."""
    response = cohere_client.embed(
        texts=[text],
        model="embed-english-light-v3.0",
        input_type="search_query"
    )
    return response.embeddings[0]


# ── ChromaDB collection (no embedding_function — we pass embeddings manually) ─
def get_collection(session_id: str):
    safe_id = session_id[:36].replace("-", "_")
    col_name = f"session_{safe_id}"
    return chroma_client.get_or_create_collection(
        name=col_name,
        metadata={"hnsw:space": "cosine"}
    )


# ── PDF helpers ───────────────────────────────────────────────────────────────
def extract_pdf_text(file_bytes: bytes) -> list[dict]:
    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and text.strip():
            pages.append({"page": i + 1, "text": text.strip()})
    return pages


def split_into_chunks(pages: list[dict], chunk_size: int = 600,
                      overlap: int = 80) -> list[dict]:
    chunks = []
    for page_data in pages:
        text = page_data["text"]
        page_num = page_data["page"]
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end]
            if chunk_text.strip():
                chunks.append({
                    "text": chunk_text,
                    "page": page_num,
                    "chunk_index": len(chunks)
                })
            start = end - overlap
            if start >= len(text) or end == len(text):
                break
    return chunks


# ── RAG helpers ───────────────────────────────────────────────────────────────
def build_citations(metadatas: list[dict], distances: list[float]) -> list[dict]:
    citation_map = {}
    for meta, dist in zip(metadatas, distances):
        if dist > 0.8:
            continue
        filename = meta.get("filename", "document")
        page = meta.get("page", "?")
        if filename not in citation_map:
            citation_map[filename] = set()
        citation_map[filename].add(page)
    return [
        {"filename": filename, "pages": sorted(list(pages))}
        for filename, pages in citation_map.items()
    ]


def build_rag_messages(question: str, chunks: list[str],
                       metadatas: list[dict], distances: list[float],
                       history: list[dict]) -> list[dict]:
    context_parts = []
    for chunk, meta, dist in zip(chunks, metadatas, distances):
        if dist > 0.8:
            continue
        source = f"[Source: {meta.get('filename', 'document')}, Page {meta.get('page', '?')}]"
        context_parts.append(f"{source}\n{chunk}")

    context = "\n\n---\n\n".join(context_parts)

    if context_parts:
        system_content = f"""You are DocuMind, an intelligent document analysis assistant.
Your job is to answer questions about uploaded documents accurately and helpfully.

IMPORTANT RULES:
1. Answer using ONLY the context provided below — do not use outside knowledge
2. If the answer is not in the context, say exactly: "I could not find this information in the uploaded documents."
3. Always mention which document and page number your answer comes from
4. Be clear, concise, and helpful
5. Use bullet points or numbered lists when listing multiple items
6. If asked about something partially covered, share what you found and note what's missing

DOCUMENT CONTEXT:
{context}"""
    else:
        system_content = """You are DocuMind, an intelligent document analysis assistant.
The uploaded documents do not appear to contain information relevant to this question.
Tell the user clearly: "I could not find relevant information about this topic in the uploaded documents."
Do not make up information or use outside knowledge."""

    messages = [{"role": "system", "content": system_content}]
    for h in history[-8:]:
        role = h.get("role", "")
        content = h.get("content", "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": question})
    return messages


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return "DocuMind Backend is Running"


@app.route("/api/health", methods=["GET"])
def health():
    try:
        collections_count = len(chroma_client.list_collections())
    except Exception as e:
        print(f"Health check error: {e}")
        collections_count = "error"
    return jsonify({
        "status": "ok",
        "service": "DocuMind",
        "chroma_path": CHROMA_PATH,
        "collections": collections_count,
        "model": MODEL,
    })


@app.route("/api/upload", methods=["POST"])
def upload():
    print("==> UPLOAD: request received")
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    session_id = request.form.get("session_id", str(uuid.uuid4()))

    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are supported"}), 400

    try:
        file_bytes = file.read()
        print(f"==> UPLOAD: file read OK, size={len(file_bytes)} bytes")
    except Exception as e:
        return jsonify({"error": f"Could not read file: {str(e)}"}), 400

    if len(file_bytes) > 10 * 1024 * 1024:
        return jsonify({"error": "File size exceeds 10MB limit"}), 400

    doc_id = hashlib.md5(file_bytes).hexdigest()[:12]

    try:
        pages = extract_pdf_text(file_bytes)
        print(f"==> UPLOAD: extracted {len(pages)} pages")
    except Exception as e:
        return jsonify({"error": f"Could not parse PDF: {str(e)}"}), 400

    if not pages:
        return jsonify({"error": "No text found in PDF"}), 400

    chunks = split_into_chunks(pages)
    print(f"==> UPLOAD: split into {len(chunks)} chunks")

    try:
        collection = get_collection(session_id)
        print("==> UPLOAD: got collection")

        already_stored = False
        try:
            test = collection.get(ids=[f"{doc_id}_0"])
            already_stored = len(test["ids"]) > 0
        except Exception:
            already_stored = False

        if already_stored:
            print(f"==> UPLOAD: duplicate detected, skipping embed")
        else:
            print(f"==> UPLOAD: calling Cohere embed API for {len(chunks)} chunks...")
            embeddings = embed_documents([c["text"] for c in chunks])
            print(f"==> UPLOAD: Cohere embed done, got {len(embeddings)} embeddings")

            collection.add(
                ids=[f"{doc_id}_{c['chunk_index']}" for c in chunks],
                documents=[c["text"] for c in chunks],
                embeddings=embeddings,
                metadatas=[{
                    "doc_id": doc_id,
                    "page": c["page"],
                    "filename": file.filename,
                } for c in chunks],
            )
            print(f"==> UPLOAD: stored {len(chunks)} chunks in ChromaDB")

    except Exception as e:
        print(f"==> UPLOAD ERROR: {str(e)}")
        return jsonify({"error": f"Failed to store chunks: {str(e)}"}), 500

    if session_id not in sessions:
        sessions[session_id] = {}
    sessions[session_id][doc_id] = {
        "name": file.filename,
        "pages": len(pages),
        "chunk_count": len(chunks),
    }

    return jsonify({
        "doc_id": doc_id,
        "session_id": session_id,
        "name": file.filename,
        "pages": len(pages),
        "chunk_count": len(chunks),
        "message": f"Indexed {len(chunks)} chunks from {len(pages)} pages"
    })


@app.route("/api/documents/<session_id>", methods=["GET"])
def list_documents(session_id):
    docs = sessions.get(session_id, {})
    return jsonify({
        "documents": [
            {
                "doc_id": doc_id,
                "name": meta["name"],
                "pages": meta["pages"],
                "chunks": meta["chunk_count"],
            }
            for doc_id, meta in docs.items()
        ]
    })


@app.route("/api/documents/<session_id>/<doc_id>", methods=["DELETE"])
def delete_document(session_id, doc_id):
    try:
        collection = get_collection(session_id)
        existing = collection.get(where={"doc_id": doc_id})
        if existing["ids"]:
            collection.delete(ids=existing["ids"])
            print(f"Deleted {len(existing['ids'])} chunks for doc {doc_id}")

        if session_id in sessions and doc_id in sessions[session_id]:
            del sessions[session_id][doc_id]

        return jsonify({
            "success": True,
            "doc_id": doc_id,
            "chunks_deleted": len(existing["ids"]) if existing["ids"] else 0
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/search", methods=["POST"])
def search():
    data = request.get_json()
    question = data.get("question", "").strip()
    session_id = data.get("session_id", "")

    if not question or not session_id:
        return jsonify({"error": "question and session_id required"}), 400

    try:
        collection = get_collection(session_id)
        if collection.count() == 0:
            return jsonify({"error": "No documents in this session"}), 400

        query_embedding = embed_query(question)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(5, collection.count()),
            include=["documents", "metadatas", "distances"]
        )

        chunks = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        formatted = []
        for chunk, meta, dist in zip(chunks, metadatas, distances):
            relevance = "high" if dist < 0.6 else "medium" if dist < 1.0 else "low"
            formatted.append({
                "text": chunk,
                "filename": meta.get("filename", "unknown"),
                "page": meta.get("page", "?"),
                "distance": round(dist, 4),
                "relevance": relevance,
            })

        return jsonify({
            "question": question,
            "results": formatted,
            "total_chunks_in_session": collection.count(),
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    question = data.get("question", "").strip()
    session_id = data.get("session_id", "").strip()
    history = data.get("history", [])

    if not question:
        return jsonify({"error": "question is required"}), 400
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400
    if len(question) > 2000:
        return jsonify({"error": "Question too long (max 2000 chars)"}), 400

    try:
        collection = get_collection(session_id)
        if collection.count() == 0:
            return jsonify({"error": "No documents found. Please upload a PDF first."}), 400

        query_embedding = embed_query(question)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(5, collection.count()),
            include=["documents", "metadatas", "distances"]
        )
        chunks = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

    except Exception as e:
        return jsonify({"error": f"ChromaDB query failed: {str(e)}"}), 500

    citations = build_citations(metadatas, distances)
    messages = build_rag_messages(question, chunks, metadatas, distances, history)

    print(f"QUESTION: {question} | SESSION: {session_id} | CHUNKS: {len(chunks)}")

    def generate():
        yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"
        try:
            stream = groq_client.chat.completions.create(
                model=MODEL,
                messages=messages,
                max_tokens=1024,
                temperature=0.3,
                stream=True,
            )
            for chunk in stream:
                text = chunk.choices[0].delta.content
                if text:
                    yield f"data: {json.dumps({'type': 'text', 'text': text})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Groq error: {str(e)}'})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"DocuMind starting on port {port}")
    app.run(host="0.0.0.0", port=port)