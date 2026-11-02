# complianceiq — Claude Code notes
_Draft by Claude, 2026-11-01 — edit to your own wording._

ComplianceIQ: citation-grounded RAG navigator for childcare-center regulations (Head Start, CDC milestones); refuses when the corpus doesn't cover a question. Phase 1 = retrieval layer. PUBLIC repo.

## Commands (README Quickstart; no CI, no Makefile, no test suite defined)
- Setup: `python3 -m venv .venv && source .venv/bin/activate && pip install -e .`, then `cp .env.example .env` (never read or print `.env`)
- `python -m scripts.download_corpus`, `python -m src.ingest`
- `python -m src.cli "<question>"`
- `python -m eval.eval > eval/results.md` (optional eval; overwrites results.md)

## Key paths
- `src/` — ingest, retrieve, generate, cli
- `eval/` — eval.py, questions.yaml, results.md; `scripts/download_corpus.py`
- `data/raw/` (corpus drop-in, gitignored), `docs/`

## Rules
- Public repo: never commit `.env`, keys, `data/raw/`, `data/chroma/`, `*.pkl`, `*.sqlite*` (see `.gitignore`). A local pre-commit hook (`.git/hooks/pre-commit` → `~/.claude/bin/secret-scan-staged.sh`) blocks staged secrets, `.env` files and data; `.claude/settings.json` denies reading/editing `.env`. Bypass only deliberately with `git commit --no-verify`.
- Local commits only; no push unless asked.
