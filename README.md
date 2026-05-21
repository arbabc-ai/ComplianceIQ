# ComplianceIQ

**Regulatory compliance navigator for childcare centers — grounded answers, cited sources, refuses to make things up.**

Center directors juggle three regulatory layers — federal *(Head Start, IDEA, ADA, COPPA)*, state *(licensing rules that change every state line)*, and accreditation *(NAEYC, NECPA)*. Guidance lives across hundreds of public PDFs. Directors make compliance mistakes — wrong staff-to-child ratios, missed milestone-tracking obligations, outdated nap-time policies — because finding *"what's required for my state, my age band, this scenario"* takes hours.

**ComplianceIQ** is the compliance + operations co-pilot built for that customer. Ask a question, get a sourced + citation-grounded answer or an explicit refusal when the regulations don't cover it.

Phase 1 (this repo) launches the **RAG retrieval layer** over public domain corpora. Phase 2 adds the structured-data layer (Snowflake-style warehouse of normalized ratios + state rules + accreditation scoring). Phase 3 adds the **agent layer** that routes structured-vs-unstructured queries via tool calling.

Part of the Velodyn AI SaaS family — alongside [BackgroundX](https://backgroundx.ai) (image processing), [ScribeFlash](https://scribeflash.ai) (healthcare transcription), and [RewriteIQ](https://rewriteiq.ai) (content rewriting).

---

## Value chain — DE → Data → RAG → Agent

```
┌────────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐
│   DE LAYER     │    │  DATA LAYER  │    │  RAG LAYER  │    │  AGENT LAYER │
│  (Phase 2)     │    │  (Phase 2)   │    │  (Phase 1)  │    │  (Phase 3)   │
├────────────────┤    ├──────────────┤    ├─────────────┤    ├──────────────┤
│ Airflow DAG    │ →  │ Snowflake /  │ →  │ Vector DB   │ ←─ │ LLM router:  │
│ ingests state  │    │ Postgres     │    │ over raw    │ ←─ │ structured?  │
│ licensing PDFs │    │ ratios_by_   │    │ regulatory  │ ←─ │ → warehouse  │
│ + Head Start   │    │ state        │    │ + guidance  │ ←─ │ unstructured?│
│ + CDC. dbt     │    │ age_bands    │    │ docs        │ ←─ │ → RAG        │
│ transforms to  │    │ accreditation│    │ + citations │ ←─ │ tool-calling │
│ normalized     │    │ standards    │    │ + refusals  │ ←─ │ + compose    │
│ rules tables   │    │ (warehouse)  │    │             │ ←─ │ final answer │
└────────────────┘    └──────────────┘    └─────────────┘    └──────────────┘
        ↑                    ↑                  ↑                    ↑
   Airflow / dbt        Snowflake /        Chroma /           Claude / GPT-4o
   ingestion +          Postgres /         Pinecone /         + tool-calling
   transformation       pgvector /         OpenSearch /       framework
                        DuckDB             AWS Bedrock KB
```

---

## Corpus (Phase 1)

All public domain — U.S. government or federally-codified sources:

| Source | What it covers | License |
|---|---|---|
| **CDC "Learn the Signs. Act Early."** | Age-banded developmental milestones (2 months → 5 years) — required tracking under Head Start + many state programs | U.S. gov public domain ✓ |
| **45 CFR Part 1302 — Head Start Program Performance Standards** | Federal regs on staff qualifications, child:staff ratios, curriculum requirements, family engagement, screening obligations | Federal regulations, public domain ✓ |
| State child-care licensing rules *(extend by dropping PDFs in `data/raw/`)* | The most-asked questions ("what's the ratio for 18-month-olds in MY state") | Each state publishes; public ✓ |
| NAEYC position statements | *Not bundled — copyrighted. Drop your own licensed copies into `data/raw/` to extend.* | NAEYC copyright ⚠️ |

Corpus expands by dropping any `.txt` / `.md` / `.pdf` into `data/raw/` and re-running `python -m src.ingest`.

---

## Design decisions

| Choice | Why |
|---|---|
| **Anthropic Claude (Sonnet)** | Cost-effective, strong instruction-following, citation-friendly. Same model family as AWS Bedrock (likely target stack for production deployment). |
| **ChromaDB local file-backed** | Zero infra; embedding store + metadata in one place. Production swap → pgvector on Postgres or OpenSearch on AWS. |
| **sentence-transformers `all-MiniLM-L6-v2`** | Free, CPU-runnable, 384-dim embeddings, solid baseline. Production swap → Cohere v3 or `text-embedding-3-large`. |
| **RecursiveCharacterTextSplitter** | Markdown-aware boundaries. 800-char chunks with 100-char overlap fit regulatory paragraph structure well. |
| **Hybrid retrieval (BM25 + dense, RRF fusion)** | Regulatory text is full of exact-phrase questions ("staff:child ratio," "performance standard 1302.42") that BM25 nails but dense paraphrases miss. Hybrid covers both. |
| **Citation enforcement** | Compliance answers without citations are unusable. The system prompt requires `[source: doc_name]` after each claim. Refuses when no relevant context retrieved. |
| **Eval = hit-rate@5 + Claude-as-judge faithfulness** | Cheap, fast, sufficient for Phase 1. Production swap → RAGAS framework or custom regulatory-domain eval. |

---

## Quickstart

```bash
# 1. Setup environment
cd ~/projects/complianceiq
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env
# Edit .env, set ANTHROPIC_API_KEY=sk-ant-...

# 2. Download the public corpus (CDC milestones + Head Start standards)
python -m scripts.download_corpus

# 3. Build the index
python -m src.ingest

# 4. Ask compliance questions
python -m src.cli "At what age must I begin developmental screening per Head Start?"
python -m src.cli "What motor milestones should I document at 6 months?"
python -m src.cli "What's the staff:child ratio for 18-month-olds in Ohio?"  # refuses if not in corpus
python -m src.cli "What is OFSAA?"  # refuses — out of domain

# 5. (Optional) Run the eval
python -m eval.eval > eval/results.md
```

---

## Project layout

```
complianceiq/
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
│   └── download_corpus.py   # Fetch CDC milestones + Head Start standards into data/raw/
├── eval/
│   ├── questions.yaml   # 12 ground-truth compliance Q&A pairs (with refusal cases)
│   └── eval.py          # Hit-rate@5 + Claude-as-judge faithfulness scoring
├── data/                # Corpus + chroma index (gitignored)
└── docs/
    └── architecture.md  # Deep dive: chunking math, RRF formula, Phase 2/3 design
```

---

## What I'd build next (Phase 2 + Phase 3 roadmap)

**Phase 2 — DE + Data layer** *(4-6 weeks post-Phase-1)*

1. **Airflow ingestion DAG** — daily DAG pulls state-by-state licensing PDFs + federal regs from canonical URLs into S3. Operators: `HTTPOperator` for URL fetch, `S3KeySensor` for arrival, `PythonOperator` for normalization. Hosted on Astronomer or AWS MWAA.
2. **Snowflake warehouse layer** — landing tables for raw docs, dbt staging models to extract structured rules (ratios, age bands, qualification minimums), marts table `compliance_rules` keyed by `(state, federal_program, age_band, rule_type)`.
3. **dbt transformations** — `stg_state_licensing → int_normalized_rules → marts/compliance_rules`. Tests on every layer: ratio values must be positive, age bands must cover 0-60 months, no overlapping rules per state.
4. **Hybrid retrieval over both** — RAG now retrieves over BOTH unstructured policy text AND structured rules table via SQL queries on the warehouse.

**Phase 3 — Agent layer** *(6-8 weeks post-Phase-2)*

1. **LLM router** — Claude with tool-calling decides per query: structured lookup (call warehouse) vs unstructured guidance (RAG) vs both.
2. **Tools** — `lookup_ratio(state, age_band)`, `lookup_qualification(role, state)`, `search_guidance(query)`, `calculate_compliance_score(center_id)`.
3. **Agent composes answer** with citations from both data + retrieval. Refuses when neither has support.

---

## Reference repos worth knowing

Public RAG implementations to study or reference in conversation:

- **[langchain-ai/rag-from-scratch](https://github.com/langchain-ai/rag-from-scratch)** — Canonical 14-notebook walkthrough.
- **[anthropics/anthropic-cookbook](https://github.com/anthropics/anthropic-cookbook)** — `skills/retrieval_augmented_generation/` + `skills/contextual-embeddings/`.
- **[pinecone-io/examples](https://github.com/pinecone-io/examples)** — Production-leaning patterns.

---

## License

Pipeline code: MIT.

Bundled corpus: U.S. government public domain (CDC milestones + 45 CFR Part 1302 Head Start standards). NAEYC content, if you add it yourself, remains NAEYC copyright — do not redistribute.

---

*ComplianceIQ is part of the [Velodyn](https://velodyn.com) AI SaaS family.*
