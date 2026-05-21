"""Prompt construction + Claude call with citations.

Programmatic use:
    from src.generate import answer
    result = answer("when do toddlers start walking?")
    # result = {"answer": "...", "sources": [...], "context_used": [...]}
"""
from __future__ import annotations

import os

from anthropic import Anthropic
from dotenv import load_dotenv

from src.retrieve import retrieve

load_dotenv()

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
MAX_TOKENS = 1024

SYSTEM_PROMPT = """You are an assistant that answers questions about early-childhood education using ONLY the provided context.

Rules:
1. Ground every factual claim in the context. After each claim, attach a citation in the form [source: <doc_name>].
2. If the context does not contain enough information to answer, say so explicitly: "The provided sources don't contain enough information to answer that." Do NOT guess or fall back to your training data.
3. Be concise. Educators and caregivers value clarity over comprehensiveness.
4. If the question is ambiguous, ask a clarifying question rather than guessing.
"""

USER_TEMPLATE = """Question: {question}

Context (retrieved chunks):
{context}

Answer the question following the rules above. Remember to cite every claim with [source: <doc_name>] and refuse if the context is insufficient."""


def _format_context(hits: list[dict]) -> str:
    lines = []
    for i, h in enumerate(hits, 1):
        lines.append(f"--- chunk {i} (source: {h['source']}) ---\n{h['text']}\n")
    return "\n".join(lines)


def answer(question: str, k: int = 5, mode: str = "hybrid") -> dict:
    hits = retrieve(question, k=k, mode=mode)
    if not hits:
        return {
            "answer": "The provided sources don't contain enough information to answer that.",
            "sources": [],
            "context_used": [],
        }

    client = Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": USER_TEMPLATE.format(
                    question=question, context=_format_context(hits)
                ),
            }
        ],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    return {
        "answer": text,
        "sources": sorted({h["source"] for h in hits}),
        "context_used": [{"source": h["source"], "chunk_index": h["chunk_index"]} for h in hits],
    }


if __name__ == "__main__":
    import sys
    question = " ".join(sys.argv[1:]) or "When do most children start to say their first words?"
    result = answer(question)
    print("\n=== ANSWER ===")
    print(result["answer"])
    print("\n=== SOURCES ===")
    for s in result["sources"]:
        print(f"  - {s}")
