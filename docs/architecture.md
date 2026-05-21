# ComplianceIQ — Architecture deep dive

This doc complements the README with the math + reasoning behind the choices, and the Phase 2 + Phase 3 design intent.

## The full value chain (DE → Data → RAG → Agent)

ComplianceIQ is built as four phases, but only **Phase 1 (the RAG layer)** is in this repo.

### Phase 2 — DE + Data layer

**The DE problem:** Childcare regulations come from 50+ sources — federal CFR, state licensing boards, accreditation bodies, county/city ordinances. Each has its own update cadence (state regs annually, federal CFR yearly, NAEYC standards every few years). Manual scraping doesn't scale.

**The Airflow shape:**
- `daily_state_licensing_ingest` DAG — `HTTPOperator` fetches per-state rule PDFs, `S3KeyOperator` lands them in S3, `PythonOperator` extracts text via `pypdf`, `SnowflakeOperator` upserts to a raw-text landing table
- `weekly_federal_regs_check` DAG — polls eCFR's update endpoint, re-ingests only changed parts
- Sensors guard against partial pulls; each DAG has SLA + Slack alerts on failure

**The dbt shape (medallion pattern):**
```
sources: raw_state_licensing_text, raw_head_start_text, raw_naeyc_text
   ↓ (staging)
stg_state_licensing_chunks, stg_head_start_chunks   (1:1 with source, light cleanup)
   ↓ (intermediate)
int_extracted_rules                                  (LLM-assisted structured extraction:
                                                      pulls ratios, age bands, qualifications
                                                      out of unstructured policy text)
   ↓ (marts)
fct_compliance_rules                                 (state × federal_program × age_band ×
                                                      rule_type, business-facing fact table)
dim_age_bands, dim_states, dim_accreditation_bodies  (conformed dimensions)
```

**The Snowflake shape:**
- Star schema: ~50K-row fact table, tens of dimension rows
- Zero-copy clones for dev/staging warehouses
- Time Travel keeps 30-day audit log of rule changes (compliance-relevant)
- Cortex `AI_CLASSIFY` (Snowflake's in-warehouse LLM) handles unstructured → structured extraction where cost-effective

### Phase 3 — Agent layer

**The agent problem:** Real compliance queries mix structured + unstructured. *"What's the staff:child ratio for my 18-month-olds and what research supports it?"* — first half is structured warehouse lookup, second half is RAG over policy/research text.

**The agent shape:**
- LLM router (Claude tool-use or OpenAI function-calling) inspects the query, decides which tools to call
- Tool definitions:
  - `lookup_ratio(state, age_band) → dict` — Snowflake SQL query
  - `lookup_qualification(role, state) → dict` — Snowflake SQL query
  - `search_guidance(query, k=5) → list[chunk]` — the RAG pipeline in this repo
  - `calculate_compliance_score(center_id) → dict` — deterministic Python over the warehouse
- Final compose step: agent receives all tool outputs, composes a grounded answer with citations from both sources, refuses when support is incomplete

**Why this shape:** Pure RAG can't answer structured questions reliably ("what's the ratio?" is a lookup, not a search). Pure SQL can't answer unstructured guidance. The agent layer routes — that's where the customer value compounds.

## Why hybrid retrieval (BM25 + dense)

Dense retrieval (embedding-based) is great at paraphrase:

- Query: *"When do babies start walking?"*
- Document: *"Most children take their first independent steps around their first birthday."*
- Dense match: ✅ (semantic similarity is high)
- BM25 match: ❌ (no shared keywords)

BM25 (lexical / tf-idf) is great at exact-term matching and acronyms:

- Query: *"NAEYC position statements"*
- Document: *"NAEYC publishes position statements..."*
- BM25 match: ✅ (rare term `NAEYC` carries high IDF weight)
- Dense match: ⚠️ (a paraphrased document about "early-childhood-education guidelines" may score similarly)

Combining the two via Reciprocal Rank Fusion captures both regimes without tuning weights.

### RRF formula

```
score(d) = sum over rankers r:  1 / (k_rrf + rank_r(d))
```

`k_rrf` (typically 60) flattens the contribution of top-ranked items so each ranker contributes meaningfully even when their ranks differ. Why 60? Cormack/Clarke/Buettcher (2009) empirically tested values from 1 to 100 and 60 was a robust default. Don't tune this.

## Chunking math

We use `RecursiveCharacterTextSplitter` with:
- chunk_size: 800 chars
- chunk_overlap: 100 chars
- separators: `["\n\n", "\n", ". ", " ", ""]`

Why 800? CDC milestone PDFs are short documents; 800 chars ≈ 200 tokens, which fits ~5-7 chunks per page. Smaller chunks (200-400) get better precision but lose context. Bigger chunks (1500+) keep more context but bring more noise into the prompt.

Why 100-char overlap? Prevents losing a fact that straddles a chunk boundary.

Why recursive (not fixed-size)? Recursive splitter tries each separator in order, falling back if needed. Result: chunks tend to break at paragraph/sentence boundaries rather than mid-word.

## Why MiniLM-L6-v2 for embeddings

- **Cost:** Free; runs locally on CPU
- **Size:** 384-dim vectors (cheap to store, fast to search)
- **Quality:** Strong baseline; well-cited in the MTEB benchmark for semantic similarity
- **Production swap:** Cohere `embed-v3` (better quality, ~$0.10/M tokens) or OpenAI `text-embedding-3-large` (3072-dim, $0.13/M tokens). Both consistently beat MiniLM on retrieval benchmarks but cost real money.

For brightwheel's stack on AWS Bedrock: **Titan embeddings** would be the in-stack choice; **Cohere v3 on Bedrock** is also available.

## Why Claude-as-judge for faithfulness eval

For a weekend build, the canonical RAG eval framework ([RAGAS](https://docs.ragas.io)) is overkill. Claude-as-judge gives us a reasonable signal in 10 lines of code:

1. Show Claude the question, the answer, and the retrieved context
2. Ask for a 0-3 score
3. Average across the eval set

This is the same technique RAGAS uses internally for faithfulness scoring. The downside is cost (1 API call per eval question) and reproducibility (LLM judges drift across model versions). For production, use RAGAS or a fine-tuned judge.

## Citation enforcement pattern

The system prompt enforces citations:

```
After each claim, attach a citation in the form [source: <doc_name>].
If the context does not contain enough information, refuse explicitly.
```

This is a soft pattern (Claude can technically violate it), but in practice Claude Sonnet follows it >95% of the time when the rule is in the system prompt. Production-grade enforcement: post-process the response with regex, reject if any sentence lacks a citation tag.

## What's missing for production

| Concern | Mitigation |
|---|---|
| Cold-start latency | Pre-warm Chroma client; cache BM25 in process |
| Index updates | Incremental ingest (don't drop the collection each run); track corpus checksums |
| Multi-tenant data | Use Chroma's `where` clause on metadata to partition by tenant |
| Cost | Switch from local sentence-transformers to a hosted embedding API only if you need quality; cache embeddings per document |
| Eval drift | Pin the judge model version; re-run on every prompt change |
| Hallucination on missing context | Post-process for citation presence; reject + retry without context if missing |
| PII / FERPA / COPPA | Filter inputs/outputs; never log user PII or child names to a vendor LLM without a BAA-equivalent agreement |
