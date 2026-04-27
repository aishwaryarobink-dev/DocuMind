""" 
DocuMind day 3
"""

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
from chromadb.utils import embedding_functions

load_dotenv()
app=Flask(__name__)
CORS(app, origins="*")

#chroma db setup
CHROMA_PATH="./chroma_store"
Path(CHROMA_PATH).mkdir(exist_ok=True)
chroma_client=chromadb.PersistentClient(path=CHROMA_PATH)
embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
    )
sessions={}

#get/creAte ChromaDB collention for session
def get_collection(session_id: str):
    safe_id= session_id[:36].replace("-","_")
    col_name=f"session_{safe_id}"
    return chroma_client.get_or_create_collection(
        name=col_name, 
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"}
    )

def extract_pdf_text(file_bytes: bytes) -> list[dict]:
    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    pages  = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and text.strip():
            pages.append({"page": i + 1, "text": text.strip()})
    return pages


def split_into_chunks(pages: list[dict], chunk_size: int = 600,
                      overlap: int = 80) -> list[dict]:
    chunks = []
    for page_data in pages:
        text     = page_data["text"]
        page_num = page_data["page"]
        start    = 0
        while start < len(text):
            end        = min(start + chunk_size, len(text))
            chunk_text = text[start:end]
            if chunk_text.strip():
                chunks.append({
                    "text":        chunk_text,
                    "page":        page_num,
                    "chunk_index": len(chunks)
                })
            start = end - overlap
            if start >= len(text) or end == len(text):
                break
    return chunks

#ROUTES
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status":       "ok",
        "service":      "DocuMind",
        "day":          3,
        "chroma_path":  CHROMA_PATH,
        "collections":  len(chroma_client.list_collections()),
    })

@app.route("/api/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files["file"]
    session_id = request.form.get("session_id", str(uuid.uuid4()))
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are supported"}), 400
    
    try:
        file_bytes=file.read()
    except Exception as e:
        return jsonify({"error": f"Could nto read file: {str(e)}"}), 400
    
    if len(file_bytes)> 10*1024*1024:
        return jsonify({"error": "File size exceeds 10MB limit"}), 400
    
    doc_id = hashlib.md5(file_bytes).hexdigest()[:12]

    try:
        pages = extract_pdf_text(file_bytes)
    except Exception as e:
        return jsonify({"error": f"Could not parse PDF: {str(e)}"}), 400
    
    if not pages:
        return jsonify({"error": "No text found!!!"}), 400
    chunks = split_into_chunks(pages)

    try: 
        collection = get_collection(session_id)
        already_stored = False
        try:
            test = collection.get(ids=[f"{doc_id}_0"])
            already_stored = len(test["ids"]) > 0
        except Exception:
            already_stored = False

        if already_stored:
            print(f"\nDuplicate detected: {file.filename} ({doc_id}) — skipping re-embed\n")
        else:
            print(f"\n{'='*60}")
            print(f"Uploading: {file.filename} | doc_id: {doc_id} | chunks: {len(chunks)}")

            collection.add(
                ids=[f"{doc_id}_{c['chunk_index']}" for c in chunks],
                documents=[c["text"] for c in chunks],
                metadatas=[{
                    "doc_id":   doc_id,
                    "page":     c["page"],
                    "filename": file.filename,
                } for c in chunks],
            )
            print(f"Stored {len(chunks)} chunks in ChromaDB")
            print(f"{'='*60}\n")

    except Exception as e:
        return jsonify({"error": f"Failed to store chunks: {str(e)}"}), 500

    # update session tracker
    if session_id not in sessions:
        sessions[session_id]={}
    sessions[session_id][doc_id]={
        "name": file.filename,
        "pages": len(pages),
        "chunk_count": len(chunks),
    }
# return to react
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
    """Return all documents in a session."""
    docs = sessions.get(session_id, {})
    return jsonify({
        "documents": [
            {
                "doc_id": doc_id,
                "name":   meta["name"],
                "pages":  meta["pages"],
                "chunks": meta["chunk_count"],
            }
            for doc_id, meta in docs.items()
        ]
    })

@app.route("/api/documents/<session_id>/<doc_id>", methods=["DELETE"])
def delete_document(session_id, doc_id):
    try:
        collection = get_collection(session_id)
        # Find all chunk IDs for this document
        existing = collection.get(where={"doc_id": doc_id})
        if existing["ids"]:
            collection.delete(ids=existing["ids"])
            print(f"\nDeleted {len(existing['ids'])} chunks for doc {doc_id}\n")

        # Remove from session tracker
        if session_id in sessions and doc_id in sessions[session_id]:
            del sessions[session_id][doc_id]

        return jsonify({
            "success":       True,
            "doc_id":        doc_id,
            "chunks_deleted": len(existing["ids"]) if existing["ids"] else 0
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/search", methods=["POST"])
def search():
    #debug endpoint
    data       = request.get_json()
    question   = data.get("question", "").strip()
    session_id = data.get("session_id", "")

    if not question or not session_id:
        return jsonify({"error": "question and session_id required"}), 400

    try:
        collection = get_collection(session_id)

        if collection.count() == 0:
            return jsonify({"error": "No documents in this session. Upload a PDF first."}), 400

        results = collection.query(
            query_texts = [question],     
            n_results   = min(5, collection.count()),
            include     = ["documents", "metadatas", "distances"]
        )

        chunks         = results["documents"][0]
        metadatas      = results["metadatas"][0]
        distances      = results["distances"][0]

        formatted = []
        for chunk, meta, dist in zip(chunks, metadatas, distances):
            relevance = "high" if dist < 0.6 else "medium" if dist < 1.0 else "low"
            formatted.append({
                "text":      chunk,
                "filename":  meta.get("filename", "unknown"),
                "page":      meta.get("page", "?"),
                "distance":  round(dist, 4),
                "relevance": relevance,
            })

        return jsonify({
            "question": question,
            "results":  formatted,
            "total_chunks_in_session": collection.count(),
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print(f"\nDocuMind backend starting...")
    print(f"ChromaDB path: {CHROMA_PATH}")
    print(f"Embedding model: all-MiniLM-L6-v2 (loads on first upload)\n")
    app.run(debug=True, port=5001, threaded=True)