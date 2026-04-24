"""
for Day 2 -- Documind

"""
from curses import meta
import os
import io
import json
import uuid
import hashlib

from flask import Flask, request, Response, stream_with_context, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import pypdf

load_dotenv()
app=Flask(__name__)
CORS(app)

sessions={} #im memory session store - resets when Flask restarts

def extract_pdf_txt(file_bytes: bytes) -> list[dict]:
    """Extract text from PDF file bytes and return a list of dictionaries containing page number and text."""
    pdf_reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    pages = []
    
    for page_num, page in enumerate(pdf_reader.pages):
        text = page.extract_text()
        if text and text.strip():  # Check if text is not empty or just whitespace
            pages.append({
                            "page": page_num, 
                            "text": text.strip()
                         })
    return pages

def split_into_chunks(pages: list[dict], chunk_size: int=600,
                      overlap: int=80) -> list[dict]:
    """Split the extracted text into chunks with specified size and overlap."""
    chunks=[]
    for data in pages:
        txt=data["text"]
        page_num=data["page"]
        start=0
        while start<len(txt):
            end = min(start+chunk_size, len(txt))
            chunk_txt= txt[start:end]
            if chunk_txt.strip():
                chunks.append({
                    "page": page_num,
                    "text": chunk_txt.strip(),
                    "chunk_id": len(chunks)
                })
            start = end - overlap
            if start>=len(txt) or end==len(txt):
                break
    return chunks

@app.route("/api/health", methods=["GET"])
def healt():
    return jsonify({
        "status": "ok",
        "service": "documind",
        "day": 2
    })

@app.route("/api/upload", methods=["POST"])
def upload():
    """
    Receive a PDF file, extract text, split into chunks.

    Request:  multipart/form-data with:
              - file:       the PDF file
              - session_id: string identifying this browser session

    Response: JSON with document metadata

    What multipart/form-data means:
        When React sends a file, it uses FormData (not JSON).
        FormData encodes the file as binary alongside text fields.
        Flask receives files in request.files and text in request.form.
        This is different from request.get_json() which only works for JSON bodies.
    """
    if "file" not in request.files:
        return jsonify({"error":"No file provided"}), 400
    
    file = request.files["file"]
    session_id=request.form.get(
        "session_id", str(uuid.uuid4())
    )
    
    #validate-----------
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error":"Invalid file type. Please upload a PDF file."}), 400
    if not session_id:
        return jsonify({"error":"No session ID provided"}), 400
    
    #read file bytes----------
    try:
        file_bytes = file.read()
    except Exception as e:
        return jsonify({"eroor": f"Could not read file: {str(e)}"}), 400
    
    #size check: 10MB limit-----------
    if len(file_bytes)>10*1024*1024:
        return jsonify({"error":"File too large. Max size is 10MB"}), 400
    
    #Generate stable doc_id
    #MD5 hash of file bytes: same pdf to get same doc_id always
    doc_id = hashlib.md5(file_bytes).hexdigest()[:12]

    #Extract txt
    try:
        pages = extract_pdf_txt(file_bytes)
    except Exception as e:
        return jsonify({"error": f"Could not parse PDF: {str(e)}"}), 400
    
    if not pages:
        return jsonify({"error": "No text found in PDF"}), 400
    
    #split into chunks----------
    chunks = split_into_chunks(pages)

    #print to terminal to verify
    print(f"\n{'='*60}")
    print(f"Uploaded: {file.filename}")
    print(f"Session:  {session_id}")
    print(f"Doc ID:   {doc_id}")
    print(f"Pages:    {len(pages)}")
    print(f"Chunks:   {len(chunks)}")
    print(f"\nSample chunk (first one):")
    print(f"  Page {chunks[0]['page']}: {chunks[0]['text'][:200]}...")
    if len(chunks) > 1:
        print(f"\nSample chunk (second one — notice the overlap):")
        print(f"  Page {chunks[1]['page']}: {chunks[1]['text'][:200]}...")
    print(f"{'='*60}\n")

    #store metadat in session, chunks in memory for now---------
    if session_id not in sessions:
        sessions[session_id]={}
    
    sessions[session_id][doc_id] = {
        "name": file.filename,
        "pages": len(pages),
        "chunk_count": len(chunks),
        "chunks": chunks,
    }

    #return metadat to REact
    return jsonify({
        "doc_id": doc_id,
        "session_id": session_id,
        "name": file.filename,
        "pages": len(pages),
        "chunk_count": len(chunks),
        "message": f"Processed {len(chunks)} chunks from {len(pages)} pages."
    })

@app.route("/api/documents/<session_id>", methods=["GET"])
def list_docs(session_id):
    #list all docs for this session
    docs= sessions.get(session_id,{})
    return jsonify({
        "documents": [
            {
                "doc_id": doc_id,
                "name": meta["name"],
                "pages": meta["pages"],
                "chunk_count": meta["chunk_count"]
            }
            for doc_id, meta in docs.items()
        ]
    })
    
@app.route("/api/documents/<session_id>/<doc_id>", methods=["DELETE"])
def delete_doc(session_id, doc_id):
    #delete doc from session
    if session_id in sessions and doc_id in sessions[session_id]:
        del sessions[session_id][doc_id]
        return jsonify({"success": True, "message": f"Document {doc_id} deleted from session {session_id}."})
    return jsonify({"error":"Document not found"}), 404

@app.route("/api/chunks/<session_id>/<doc_id>", methods=["GET"])
def get_chunks(session_id, doc_id):
    #get all chunks for this doc
    doc= sessions.get(session_id,{}).get(doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    return jsonify({
        "doc_id": doc_id,
        "name": doc["name"],
        "chunks": doc["chunks"][:5],
        "total": doc["chunk_count"],
    })

if __name__ == "__main__":
    app.run(debug=True, port=5001, threaded=True)