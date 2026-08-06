"""Quick retrieval smoke test: py smoke_test.py"""
from app import vectorstore

for q in [
    "advice about running a business leadership",
    "turning point unexpected moment in career",
]:
    print(f"\n=== {q}")
    for h in vectorstore.search(q, limit=3):
        print(f"[{h['score']}] {h['source']} ~{h['ts_start']} p.{h['page_start']}")
        print("   " + h["text"][:180].replace("\n", " / "))
