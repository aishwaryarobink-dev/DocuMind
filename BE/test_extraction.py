import sys
import io
import pypdf

def extract_pdf_txt(file_bytes):
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

def split_into_chunks(pages, chunk_size=600, overlap=80):
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

if __name__ == "__main__":
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "test.pdf"

    print(f"\nLoading: {pdf_path}")
    with open(pdf_path, "rb") as f:
        file_bytes = f.read()

    print(f"File size: {len(file_bytes) / 1024:.1f} KB")

    # Extract
    pages = extract_pdf_txt(file_bytes)
    print(f"\nExtracted {len(pages)} pages with text")

    for p in pages[:3]:  # show first 3 pages
        print(f"\n  Page {p['page']} ({len(p['text'])} chars):")
        print(f"  '{p['text'][:150]}...'")

    # Chunk
    chunks = split_into_chunks(pages)
    print(f"\nSplit into {len(chunks)} chunks (size=600, overlap=80)")

    # Show first 3 chunks to verify overlap
    print("\n--- First 3 chunks (verify overlap between consecutive chunks) ---")
    for i, chunk in enumerate(chunks[:3]):
        print(f"\nChunk {i} (page {chunk['page']}):")
        print(f"  '{chunk['text'][:250]}'")

    # Show overlap between chunk 0 and chunk 1
    if len(chunks) >= 2:
        print("\n--- Overlap verification ---")
        end_of_0   = chunks[0]["text"][-80:]   # last 80 chars of chunk 0
        start_of_1 = chunks[1]["text"][:80]    # first 80 chars of chunk 1
        print(f"End of chunk 0:   '...{end_of_0}'")
        print(f"Start of chunk 1: '{start_of_1}...'")
        print("^ These should overlap (share similar text)")

    # Test different chunk sizes
    print("\n--- Chunk size comparison ---")
    for size in [300, 600, 1000]:
        c = split_into_chunks(pages, chunk_size=size)
        print(f"  chunk_size={size}: {len(c)} chunks")

    print("\n✓ Test complete. Check the output above.")