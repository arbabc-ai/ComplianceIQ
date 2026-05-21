# Architecture deep dive

This doc complements the README with the math + reasoning behind the choices.

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
