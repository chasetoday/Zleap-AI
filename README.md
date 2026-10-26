# AI Knowledge Assistant Evaluation

**Independent portfolio project | 2026-10-26 | Synthetic enterprise policy corpus**

A small-scale evaluation of Qwen (`qwen3.7-plus`) on 30 synthetic employee-policy QA tasks, comparing **full-context prompting** with an auditable, **section-level BM25 lexical RAG** prototype. This independent simulation was not commissioned by or conducted with Zleap or any employer.

## Main result — preliminary 30-case comparison

| Rubric dimension | Full-context | BM25 RAG (top-k=5) |
|---|---:|---:|
| Factual correctness | 27/30 | 29/30 |
| Citation correctness | 29/30 | 30/30 |
| Answer completeness | 30/30 | 30/30 |
| Groundedness | 27/30 | 29/30 |
| **All four pass** | **26/30 (86.7%)** | **29/30 (96.7%)** |

**Token use (30 cases with complete API logs for both conditions):** 25,170 total tokens for full-context versus 18,641 for RAG, a **25.94% reduction**. The formerly missing TC005 full-context raw API record has now been recovered and validated, enabling all 30 case pairs.

**Observed error shifts:** TC007, TC014 and TC025 passed under RAG after failing one or more dimensions under full-context prompting. TC028 still has an internal contradiction about available paid-leave quota. No new material RAG failures observed in this single run.

**Critical limitations:** Preliminary AI-assisted rubric review, **not independent human blind rating**. Only two short fictional policy documents and one run per case. Benchmark cases were iteratively developed; top-k was tuned after looking at development results. This does **not** establish that RAG improves real-world accuracy or prove a causal effect. RAG is lexical BM25, **not** embedding/vector retrieval or a production deployment.


**Spreadsheet viewing:** `data/benchmark.csv` consolidates the datasets, contains the questions, references and preliminary ratings for 34 cases (4 Pilot and 30 Benchmark). For paired usage, see `outputs/paired_comparison_30.csv`. The original model responses are preserved in the public API logs.

## Evaluation flow

```text
Two synthetic versioned policy docs -> section chunking -> Chinese character-bigram BM25
                                      -> top-5 retrieved evidence -> Qwen API -> response + citations

Full-context comparator: two synthetic policy docs (or KB-001 where specified)
                                      -> Qwen API -> response + citations
```

## Evidence and reproducibility

- `docs/PRD.md`: proposed product improvements (not implemented).
- `outputs/evaluation_report.md`: baseline evaluation report and rubric.
- `outputs/evaluation_comparison.md`: new paired RAG comparison and error analysis.
- `outputs/scoring_benchmark_30.csv`: baseline preliminary ratings.
- `outputs/scoring_rag_30.csv`: RAG preliminary ratings and notes.
- `outputs/paired_comparison_30.csv`: per-case paired token usage and retrieved IDs for all 30 cases.
- `outputs/public_runs/`: 30 sanitized full-context API records + 30 sanitized RAG API records.
- `outputs/metrics_comparison.json`: machine-readable summary.
- `data/benchmark.csv`: 30 frozen benchmark questions and reference answers (4 earlier Pilot cases are separate).
- `knowledge_base/`: synthetic documents and provenance notes.
- `scripts/03_run_qwen.py`, `06_run_rag.py`: independent API workflows; `07_summarize_comparison.py`: offline consistency checks and aggregation.

```bash
python scripts/02_validate_knowledge_base.py
python scripts/04_validate_benchmark_v02.py
python scripts/07_summarize_comparison.py  # reads existing public records, no network/fee
```

For an offline retrieval example:

```bash
python scripts/06_run_rag.py --dry-run --start-case TC009 --limit 1 --top-k 5
```

**Live API requests require explicit `--run`, credentials and real costs.** The script reads a locally provided region-matching DashScope API Key via `DASHSCOPE_API_KEY` or terminal secure input. Do not commit credentials, `.env` files, or unredacted local API output. Public logs have provider request identifiers removed.

**Repository note:** `outputs/dataset_audit.json` is the historical audit for the initial 14-case draft, not the final 34-case dataset. `scripts/01_prepare_dataset.py` is an archival import utility that requires the original raw Feishu export, which is not included in this public repository. Current validation uses `data/benchmark.csv`.

## Authorship and boundaries

Generative AI assisted project scoping, code preparation, and preliminary scoring; the project owner prepared the test corpus, operated local scripts/API calls, and inspected outcomes. The project is an evaluation/portfolio prototype, not evidence of professional production deployment, an employer-sponsored internship, independent blind annotation, or mastery of full-stack RAG engineering. The proposed PRD in `docs/PRD.md` is not implemented or A/B tested.
