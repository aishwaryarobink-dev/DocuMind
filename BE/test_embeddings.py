from sentence_transformers import SentenceTransformer
import numpy as np

print("Loading model... (downlloads ~80MB)")
model = SentenceTransformer("all-MiniLM-L6-v2")
print("Model Loaded!\n")

#basic embedding ---- test 1
text= "Patient has chest pain and shortness of breath."
vector = model.encode(text)

print(f"Text: '{text}'")
print(f"Embedding shape: {vector.shape}")
print(f"Embedding (first 5 values): {vector[:5]}")  
print(f"vector norm: {np.linalg.norm(vector):.4f}\n")

# test 2 --- Semantice similarity
print("="*60)
print("SEMANTIC SIMILARITY TEST \n")
print("="*60)

sentences = [
    "chest pain and shortness of breath",         # query
    "cardiac symptoms with difficulty breathing",  # different words, same meaning
    "prescribed Metformin 500mg twice daily",      # medical but different topic
    "blood pressure medication dosage",            # related medical
    "python programming tutorial for beginners",   # completely unrelated
]

#encode all at once
vectors = model.encode(sentences)

query_vec = vectors[0]
print(f"\nQuery: {sentences[0]}\n")
print(f"{'Similarity':>10} Text")
print("-"*70)

for i in range(1,len(sentences)):
    #cosine similarity = dot product of norm vectors
    sim = np.dot(query_vec, vectors[i]) / (
        np.linalg.norm(query_vec) * np.linalg.norm(vectors[i])
    )
    bar= "#" * int(sim*30)
    print(f"  {sim:.4f}  {bar} '{sentences[i]}'")

#Test 3 --- chromaDB integration
print("\n" + "="*60)
print("CHROMADB INTEGRATION TEST")
print("="*60)

import chromadb
from chromadb.utils import embedding_functions

#create in memory client for testing
client = chromadb.Client()
embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
    )
collection = client.create_collection(
    name="test_collection", 
    embedding_function=embed_fn,
    metadata={"hnsw:space": "cosine"}
    )
chunks = [
    {"id": "c0", "text": "Patient was prescribed Metformin 500mg twice daily for blood sugar control.", "page": 3},
    {"id": "c1", "text": "Blood pressure readings: 140/90 mmHg. Hypertension noted.", "page": 4},
    {"id": "c2", "text": "Chest pain reported for 2 days, radiating to left arm.", "page": 1},
    {"id": "c3", "text": "Patient allergic to penicillin. No other known drug allergies.", "page": 2},
    {"id": "c4", "text": "Follow-up appointment scheduled in 4 weeks.", "page": 8},
]

collection.add(
    ids=[c["id"] for c in chunks],
    documents=[c["text"] for c in chunks],
    metadatas=[{"page": c["page"]} for c in chunks]
)

print(f"Added {len(chunks)} chunks to ChromaDB collection.\n" )
print(f"Total vectors in collection: {collection.count()}\n")

#Query
queries = [
    "What medication was prescribed?",
    "What are the heart symptoms?",
    "Any drug allergies?",
]

for q in queries:
    results=collection.query(
        query_texts=[q],
        n_results=2,    
        include= ["documents", "metadatas", "distances"]
    )
    print(f"\nQuery: '{q}'")
    for doc, meta, dist in zip(
        results["documents"][0], 
        results["metadatas"][0], 
        results["distances"][0]
        ):
        rel =" relevant " if dist < 0.8 else "~ maybe" if dist<1.2 else "not relevant"
        print(f"  {rel} (dist={dist:.3f}) Page {meta['page']}: {doc[:70]}...")
    print()
print("All tests completed!")