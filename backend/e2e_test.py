"""End-to-end test through the running API: 3 preset questions + 1 off-topic."""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def post(path, body):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


session = post("/api/sessions", {"title": "e2e test"})
print("session:", session["id"])

questions = [
    "What's one piece of advice this executive gives about running a business?",
    "What challenge, mistake, or setback do they mention facing?",
    "What's a turning point or unexpected moment they mention in their career?",
    "What does this executive think about cryptocurrency regulation in Japan?",
]

for q in questions:
    print("\n" + "=" * 80)
    print("Q:", q)
    res = post("/api/ask", {"session_id": session["id"], "question": q})
    print("covered:", res["covered"])
    print("A:", res["answer"])
    for c in res["citations"]:
        print(
            f"  [{c['marker']}] {c['source']} | {', '.join(c['speakers'])} | "
            f"~{c['ts_start']} | p.{c['page_start']}-{c['page_end']}"
        )
        print(f"      \"{c['quote'][:140]}\"")
    print("trace:", " -> ".join(s["step"] for s in res["trace"]))
