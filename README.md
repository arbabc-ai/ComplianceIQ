# early-ed-rag

A small, working RAG pipeline over early-childhood-education public guidance documents — built as an interview-prep artifact for the brightwheel Staff AI Product Builder screening.

**Stack:** Python 3.11+ · Anthropic Claude · ChromaDB · sentence-transformers · BM25 · LangChain text splitters

**What it demonstrates:**
- End-to-end RAG: ingest → chunk → embed → hybrid retrieve → augmented generation with citations
- Software-engineering discipline: clear module boundaries, small testable pieces, runnable from a single CLI
- Production-leaning concerns: hybrid retrieval (BM25 + dense), citation grounding, a faithfulness eval harness

---

## Architecture

```
┌──────────────┐    ┌──────────┐    ┌────────────┐    ┌─────────────┐
│ Public early │ →  │  Chunk   │ →  │  Embed     │ →  │  ChromaDB   │
│ ed documents │    │ (recurs.)│    │ (MiniLM)   │    │  + BM25     │
└──────────────┘    └──────────┘    └────────────┘    └──────┬──────┘
                                                             │
   ┌─────────────┐    ┌─────────┐    ┌──────────────┐        │
   │  User query │ →  │  Hybrid │ ←─ │  RRF fusion  │ ←──────┘
   └─────────────┘    │  search │    └──────────────┘
                      └────┬────┘
                           │ top-k chunks
                           ▼
                ┌──────────────────────┐
                │  Prompt + context    │
                │      Claude Sonnet   │
                └──────────┬───────────┘
                           │ answer + [citations]
                           ▼
                   ┌───────────────┐
                   │   stdout      │
                   └───────────────┘
```

## Design decisions

| Choice | Why |
|---|---|
| **Anthropic Claude (Sonnet)** | Cost-effective, strong instruction-following, citation-friendly. AWS Bedrock-equivalent (brightwheel's stack) using the same model family. |
| **ChromaDB local file-backed** | Zero infra; embedding store + metadata in one place. Production swap → pgvector or OpenSearch on AWS. |
| **sentence-transformers `all-MiniLM-L6-v2`** | Free, runs on CPU, ~384-dim embeddings, good baseline. Production swap → Cohere v3 or `text-embedding-3-large`. |
| **RecursiveCharacterTextSplitter** | Markdown-aware, predictable boundaries. 800-char chunks with 100-char overlap. |
| **Hybrid retrieval (BM25 + dense, RRF fusion)** | Dense alone misses keyword matches (acronyms, exact-phrase domain terms). BM25 alone misses paraphrase. RRF (Reciprocal Rank Fusion) combines without tuning weights. |
| **Citation enforcement in prompt** | Output schema requires `[source: doc_name]` tags after each claim. Refuses when no relevant context retrieved. |
| **Eval = hit-rate@5 + Claude-as-judge faithfulness** | Cheap, fast, sufficient for a weekend build. Production swap → RAGAS framework. |

## Quickstart

```bash
# 1. Setup environment
cd ~/projects/early-ed-rag
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env
# Edit .env, set ANTHROPIC_API_KEY=sk-ant-...

# 2. Download the public corpus (CDC developmental milestones — public domain)
python -m scripts.download_corpus

# 3. Build the index
python -m src.ingest

# 4. Ask a question
python -m src.cli "At what age do most children start to say their first words?"

# 5. (Optional) Run the eval
python -m eval.eval
```

## Project layout

```
early-ed-rag/
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── src/
│   ├── ingest.py        # Load docs → chunk → embed → ChromaDB + BM25 index
│   ├── retrieve.py      # Hybrid retrieval with RRF fusion
│   ├── generate.py      # Prompt construction + Claude call with citations
│   └── cli.py           # python -m src.cli "your question"
├── scripts/
│   └── download_corpus.py   # Fetch CDC milestones PDFs into data/raw/
├── eval/
│   ├── questions.yaml   # 10 ground-truth Q&A pairs
│   └── eval.py          # Hit-rate@5 + Claude-as-judge faithfulness scoring
├── data/                # Corpus + chroma index (gitignored)
└── docs/
    └── architecture.md  # Deeper dive: chunking math, RRF formula, eval methodology
```

## What I'd do next (production roadmap)

1. **Contextual retrieval** (Anthropic-style) — prepend each chunk with a doc-level Claude-generated summary before embedding. Empirically lifts retrieval ~50%.
2. **Cohere Rerank or BGE cross-encoder** — re-score top-50 → top-5 for final precision.
3. **AWS Bedrock Knowledge Bases parity** — re-implement on Bedrock with Titan embeddings + OpenSearch vector engine. Compare cost + latency + retrieval quality vs the local stack.
4. **Query rewriting / multi-query** — Claude generates 3-5 query variants, retrieve for each, union.
5. **Freshness / index refresh story** — incremental re-indexing when corpus changes (CDC publishes updates).
6. **RAGAS eval framework** — replace hand-rolled scoring with the canonical RAG eval library.

## Reference repos worth knowing

Public RAG implementations to study, fork-as-backup, or reference in conversation:

- **[langchain-ai/rag-from-scratch](https://github.com/langchain-ai/rag-from-scratch)** — Canonical educational walkthrough; 14 notebooks covering query translation, routing, indexing, retrieval, generation. Best single resource for understanding the design space.
- **[anthropics/anthropic-cookbook](https://github.com/anthropics/anthropic-cookbook)** — `skills/retrieval_augmented_generation/` and `skills/contextual-embeddings/` directly relevant. Contextual retrieval notebook is the productized version of Anthropic's 50%-better technique.
- **[pinecone-io/examples](https://github.com/pinecone-io/examples)** — Production-leaning patterns; especially the eval-driven examples.

## License

The pipeline code is MIT-licensed. The corpus (CDC public-domain developmental milestone materials, downloaded by `scripts/download_corpus.py`) is U.S. government work and free of copyright. NAEYC content, if substituted, is copyrighted by NAEYC — do not redistribute.
