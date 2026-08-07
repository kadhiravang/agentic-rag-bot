"""Agentic RAG graph (LangGraph): rewrite -> retrieve -> grade -> answer,
with one retrieval retry and a grounded refusal path.

LLM: Google Gemini (google-genai SDK, GEMINI_API_KEY). Structured outputs are
enforced with response_schema so citations always parse.

Grounding contract: answers come ONLY from retrieved transcript chunks. If the
evidence doesn't cover the question, the agent says so instead of guessing.
"""

import json
from typing import Any, TypedDict

from google import genai
from google.genai import types
from langgraph.graph import END, StateGraph

from . import config, vectorstore

_client: genai.Client | None = None


def get_llm() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client()  # reads GEMINI_API_KEY / GOOGLE_API_KEY
    return _client


def _generate(model: str, system: str, prompt: str, schema: dict | None = None,
              max_tokens: int = 2048) -> str:
    cfg = types.GenerateContentConfig(
        system_instruction=system,
        max_output_tokens=max_tokens,
        **(
            {"response_mime_type": "application/json", "response_schema": schema}
            if schema
            else {}
        ),
    )
    response = get_llm().models.generate_content(
        model=model, contents=prompt, config=cfg
    )
    return response.text or ""


class AgentState(TypedDict, total=False):
    question: str
    session_id: str
    query: str
    retries: int
    retrieved: list[dict]
    graded: list[dict]
    covered: bool
    answer: str
    citations: list[dict]
    trace: list[dict]


# ---------------------------------------------------------------- nodes

def rewrite_query(state: AgentState) -> AgentState:
    retry_note = (
        " The previous retrieval attempt found nothing relevant, so produce a "
        "meaningfully different query (synonyms, different angle)."
        if state.get("retries", 0) > 0
        else ""
    )
    query = _generate(
        config.GRADER_MODEL,
        system=(
            "You turn a user question about executive interview transcripts into a "
            "short search query for semantic retrieval. Return only the query text."
            + retry_note
        ),
        prompt=state["question"],
        max_tokens=256,
    ).strip()
    trace = state.get("trace", []) + [
        {"step": "rewrite_query", "detail": query, "retry": state.get("retries", 0)}
    ]
    return {"query": query or state["question"], "trace": trace}


def retrieve(state: AgentState) -> AgentState:
    hits = vectorstore.search_balanced(state["query"], session_id=state["session_id"])
    trace = state.get("trace", []) + [
        {
            "step": "retrieve",
            "detail": f"{len(hits)} chunks from Qdrant, balanced across both "
            f"transcripts (top score {hits[0]['score'] if hits else 'n/a'})",
        }
    ]
    return {"retrieved": hits, "trace": trace}


GRADE_SCHEMA = {
    "type": "object",
    "properties": {
        "relevant_indices": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "0-based indices of chunks that contain information "
            "usable to answer the question",
        }
    },
    "required": ["relevant_indices"],
}


def grade(state: AgentState) -> AgentState:
    chunks = state["retrieved"]
    if not chunks:
        return {
            "graded": [],
            "trace": state.get("trace", []) + [{"step": "grade", "detail": "no chunks to grade"}],
        }
    listing = "\n\n".join(
        f"[{i}] (from {c['source']})\n{c['text'][:1200]}" for i, c in enumerate(chunks)
    )
    raw = _generate(
        config.GRADER_MODEL,
        system=(
            "You are a strict relevance grader for a RAG pipeline over interview "
            "transcripts. Given a question and candidate chunks, return the indices "
            "of chunks that actually help answer the question. Small talk, mic "
            "checks, and off-topic banter are not relevant. If nothing helps, "
            "return an empty list."
        ),
        prompt=f"Question: {state['question']}\n\nCandidate chunks:\n\n{listing}",
        schema=GRADE_SCHEMA,
        max_tokens=512,
    )
    idxs = json.loads(raw)["relevant_indices"]
    graded = [chunks[i] for i in idxs if 0 <= i < len(chunks)]
    trace = state.get("trace", []) + [
        {"step": "grade", "detail": f"{len(graded)}/{len(chunks)} chunks passed relevance grading"}
    ]
    return {"graded": graded, "trace": trace}


def route_after_grade(state: AgentState) -> str:
    if state["graded"]:
        return "answer"
    if state.get("retries", 0) < config.MAX_RETRIEVAL_RETRIES:
        return "retry"
    return "not_covered"


def bump_retry(state: AgentState) -> AgentState:
    return {"retries": state.get("retries", 0) + 1}


ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "covered": {
            "type": "boolean",
            "description": "true only if the transcripts contain enough information "
            "to answer the question",
        },
        "answer": {
            "type": "string",
            "description": "The answer, with inline citation markers like [1], [2] "
            "referring to the numbered source chunks. If not covered, a short "
            "statement that the topic wasn't covered in the provided transcripts.",
        },
        "cited_chunks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "marker": {"type": "integer"},
                    "quote": {
                        "type": "string",
                        "description": "Short verbatim quote from that chunk supporting the answer",
                    },
                },
                "required": ["marker", "quote"],
            },
        },
    },
    "required": ["covered", "answer", "cited_chunks"],
}

ANSWER_SYSTEM = """You are the Executive Oracle: a grounded Q&A assistant over Salvi's \
Executive House interview transcripts.

Hard rules:
- Answer ONLY from the numbered source chunks provided. Never use outside knowledge \
about these people or companies.
- Every claim must carry an inline citation marker [n] pointing at the chunk it came from.
- Quote or closely paraphrase what was actually said; attribute statements to the \
right speaker.
- If the chunks do not contain an answer, set covered=false and say plainly that \
this wasn't covered in the provided transcripts. Never guess or infer.
- Source chunks may come from more than one document. When several documents have \
relevant material, cover each briefly rather than only one; if only one does, \
answer from that one alone.
- Keep answers focused: 2-6 sentences unless the question demands more."""


def answer(state: AgentState) -> AgentState:
    chunks = state["graded"]
    listing = "\n\n".join(
        f"[{i + 1}] Source: {c['source']} | Speakers: {', '.join(c['speakers'])} | "
        f"Timestamps ~{c['ts_start']}-{c['ts_end']} | Pages {c['page_start']}-{c['page_end']}\n"
        f"{c['text']}"
        for i, c in enumerate(chunks)
    )
    raw = _generate(
        config.ANSWER_MODEL,
        system=ANSWER_SYSTEM,
        prompt=f"Question: {state['question']}\n\nSource chunks:\n\n{listing}",
        schema=ANSWER_SCHEMA,
        max_tokens=4096,
    )
    parsed = json.loads(raw)
    citations = []
    for cited in parsed.get("cited_chunks", []):
        marker = cited["marker"]
        if 1 <= marker <= len(chunks):
            c = chunks[marker - 1]
            citations.append(
                {
                    "marker": marker,
                    "source": c["source"],
                    "speakers": c["speakers"],
                    "ts_start": c["ts_start"],
                    "ts_end": c["ts_end"],
                    "page_start": c["page_start"],
                    "page_end": c["page_end"],
                    "quote": cited["quote"],
                    "chunk_id": c["chunk_id"],
                    "score": c["score"],
                }
            )
    trace = state.get("trace", []) + [
        {"step": "answer", "detail": f"grounded answer with {len(citations)} citations"}
    ]
    return {
        "covered": parsed["covered"],
        "answer": parsed["answer"],
        "citations": citations,
        "trace": trace,
    }


def not_covered(state: AgentState) -> AgentState:
    trace = state.get("trace", []) + [
        {"step": "not_covered", "detail": "no relevant evidence after retry - refusing to guess"}
    ]
    return {
        "covered": False,
        "answer": "This wasn't covered in the provided transcripts.",
        "citations": [],
        "trace": trace,
    }


# ---------------------------------------------------------------- graph

def build_graph():
    g = StateGraph(AgentState)
    g.add_node("rewrite_query", rewrite_query)
    g.add_node("retrieve", retrieve)
    g.add_node("grade", grade)
    g.add_node("bump_retry", bump_retry)
    g.add_node("answer", answer)
    g.add_node("not_covered", not_covered)

    g.set_entry_point("rewrite_query")
    g.add_edge("rewrite_query", "retrieve")
    g.add_edge("retrieve", "grade")
    g.add_conditional_edges(
        "grade",
        route_after_grade,
        {"answer": "answer", "retry": "bump_retry", "not_covered": "not_covered"},
    )
    g.add_edge("bump_retry", "rewrite_query")
    g.add_edge("answer", END)
    g.add_edge("not_covered", END)
    return g.compile()


_graph = None


def ask(question: str, session_id: str) -> dict[str, Any]:
    global _graph
    if _graph is None:
        _graph = build_graph()
    result = _graph.invoke(
        {"question": question, "session_id": session_id, "retries": 0, "trace": []}
    )
    return {
        "answer": result["answer"],
        "covered": result["covered"],
        "citations": result.get("citations", []),
        "trace": result.get("trace", []),
    }
