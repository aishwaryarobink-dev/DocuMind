import sys
import requests

SESSION_ID = sys.argv[1] if len(sys.argv) > 1 else "day3-test"
BASE_URL   = "http://localhost:5001"

def search(question):
    res = requests.post(
        f"{BASE_URL}/api/search",
        json={"question": question, "session_id": SESSION_ID}
    )
    return res.json()

def print_results(question, data):
    print(f"\nQuery: '{question}'")
    if "error" in data:
        print(f"  Error: {data['error']}")
        return
    print(f"Found {len(data['results'])} results (total chunks: {data['total_chunks_in_session']})")
    for i, r in enumerate(data["results"]):
        bar = "█" * int((1.5 - r["distance"]) * 20)
        print(f"  [{i+1}] {r['relevance'].upper()} (dist={r['distance']:.3f}) {bar}")
        print(f"       Page {r['page']} | {r['filename']}")
        print(f"       '{r['text'][:120]}...'")

# Run a series of searches
questions = [
    "What is the main diagnosis?",
    "What medications were prescribed?",
    "What are the symptoms?",
    "When is the follow-up appointment?",
    "What are the test results?",
    "Does the patient have any allergies?",
]

print(f"\nSearching in session: {SESSION_ID}")
print("="*70)

for q in questions:
    result = search(q)
    print_results(q, result)

print("\n" + "="*70)
print("Search quality check:")
print("  - High relevance (dist < 0.6): directly answers the question")
print("  - Medium relevance (dist < 1.0): related context")
print("  - Low relevance (dist > 1.0): ChromaDB is just returning what it has")
print("\nIf ALL results are low relevance: the question doesn't match document content")
print("If TOP result is high relevance: RAG pipeline will work correctly")