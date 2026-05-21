"""Eval harness: hit-rate@5 + Claude-as-judge faithfulness scoring.

Run: python -m eval.eval
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml
from anthropic import Anthropic
from dotenv import load_dotenv

from src.generate import answer
from src.retrieve import retrieve

load_dotenv()

QUESTIONS_PATH = Path("eval/questions.yaml")
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

FAITHFULNESS_PROMPT = """You are evaluating whether an AI-generated answer is faithful to the source context.

Question: {question}

Answer: {answer}

Source context that was retrieved:
{context}

Rate the answer's faithfulness on a 0-3 scale:
- 3: Every factual claim in the answer is directly supported by the source context.
- 2: Most claims are supported; minor inferences are reasonable.
- 1: Some claims are unsupported or contradicted by the source.
- 0: The answer hallucinates substantially beyond the source.

Respond with ONLY a single digit (0, 1, 2, or 3). No explanation, no other text."""


def _judge_faithfulness(client: Anthropic, question: str, ans_text: str, hits: list[dict]) -> int:
    context = "\n".join(f"({h['source']}) {h['text']}" for h in hits)
    response = client.messages.create(
        model=MODEL,
        max_tokens=4,
        messages=[
            {
                "role": "user",
                "content": FAITHFULNESS_PROMPT.format(
                    question=question, answer=ans_text, context=context
                ),
            }
        ],
    )
    raw = "".join(b.text for b in response.content if b.type == "text").strip()
    try:
        return int(raw[0])
    except (ValueError, IndexError):
        return -1


def main() -> None:
    questions = yaml.safe_load(QUESTIONS_PATH.read_text())["questions"]
    client = Anthropic()

    results: list[dict] = []
    for q in questions:
        question = q["question"]
        expected_sources = set(q.get("expected_sources", []))

        # Retrieval-side scoring
        hits_for_eval = retrieve(question, k=5, mode="hybrid")
        retrieved_sources = {h["source"] for h in hits_for_eval}
        hit_at_5 = bool(expected_sources & retrieved_sources)

        # Generation-side scoring
        gen = answer(question, k=5, mode="hybrid")
        faith_score = _judge_faithfulness(client, question, gen["answer"], hits_for_eval)

        results.append(
            {
                "question": question,
                "hit_at_5": hit_at_5,
                "faithfulness": faith_score,
                "retrieved": list(retrieved_sources),
                "expected": list(expected_sources),
                "answer": gen["answer"][:200],
            }
        )

    # Aggregate
    n = len(results)
    hits = sum(1 for r in results if r["hit_at_5"])
    avg_faith = (
        sum(r["faithfulness"] for r in results if r["faithfulness"] >= 0)
        / max(1, sum(1 for r in results if r["faithfulness"] >= 0))
    )

    # Emit markdown report
    print("# RAG Eval Report\n")
    print(f"- **Questions:** {n}")
    print(f"- **Hit-rate@5:** {hits}/{n} = {hits / n:.0%}")
    print(f"- **Mean faithfulness (0-3):** {avg_faith:.2f}")
    print()
    print("| # | Hit@5 | Faith | Question | Retrieved | Expected |")
    print("|---|---|---|---|---|---|")
    for i, r in enumerate(results, 1):
        retrieved_str = ", ".join(sorted(r["retrieved"]))
        expected_str = ", ".join(sorted(r["expected"]))
        print(
            f"| {i} | {'✅' if r['hit_at_5'] else '❌'} | {r['faithfulness']} | "
            f"{r['question'][:60]} | {retrieved_str[:50]} | {expected_str[:40]} |"
        )


if __name__ == "__main__":
    main()
