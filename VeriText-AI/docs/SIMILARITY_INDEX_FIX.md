# Similarity index exceeding 100 % — cause, fix and verification

Scope: one calculation bug in the existing engine. Nothing was rebuilt, no thresholds, models,
front-end layouts or API shapes were changed.

## 1. What was wrong

The headline index was computed as

```
weighted_index = sum(similarity of every row in `counted`) / len(eligible_a_sentences)
```

`counted` deliberately holds **every** qualifying primary evidence row, and that includes
`reverse_only` rows — B→A primaries that exist so that Document B's coverage is complete even when
the pair was already accounted for in the forward direction. The numerator therefore contained more
terms than the denominator has sentences, so a many-to-one arrangement (one A sentence matched by
several B sentences) pushed the ratio above 1.0. This was an aggregation bug, not a similarity or
threshold problem: the individual cosine scores were correct and already in [0, 1].

Reproduced before any edit with a synthetic pair — 5 sentences in A, four paraphrases of each in B:
index **392.7 %**, with 20 "primary matches" reported for 5 comparable sentences (15 of them
reverse-only).

## 2. What changed (smallest correct change)

`backend/services/plagiarism_detector.py`, in the scoring stage only:

- New internal map `primary_by_source` → `primary_evidence_a`: at most **one** evidence row per
  sentence id of Document A (the highest cosine), ordered by source index. This is the evidence set
  the headline metrics are computed from.
- `counted` is untouched for everything that legitimately needs all rows: Document B coverage,
  many-to-one grouping, the detailed evidence list.
- `counts` (exact / near-exact / semantic / paraphrase) are derived from `primary_evidence_a`, so
  classification totals add up to the matched-sentence count.
- Passage clustering runs on `primary_evidence_a`, so duplicated evidence can neither invent nor
  break a consecutive-sentence run.
- `weighted_index = best_of_a.sum() / len(eligible_a)`, then clamped — the clamp is a float guard
  only; the bound now comes from the construction.
- `average_matched` and `max_similarity` were split: average over best-of-A, max over all evidence.
- `summary` gains `primary_matches` (matched sentences in A), `evidence_rows` (all qualifying pairs)
  and `reverse_only_evidence`; `explanation_of_weighted_index` was rewritten to state the formula
  and that one contribution per sentence is what keeps it ≤ 100 %.

Front end, PDF and docs (labels only, no redesign, no duplicated maths):

| File | Change |
| --- | --- |
| `frontend/src/pages/AnalysisResults.jsx` | "Primary matches" hint now shows evidence rows separately; chart footnote states "each matched sentence in A, counted once". |
| `frontend/src/pages/Methodology.jsx` | Formula caption and a paragraph on direction/reverse-only evidence. |
| `backend/services/report_generator.py` | Rows "Average similarity of matched sentences", "Matched sentences in Document A (primary evidence)", corrected index definition. |
| `README.md`, `docs/API.md`, `docs/VIVA_GUIDE.md` | §10.6 metric definitions, API field descriptions, two viva questions on the bound. |
| `backend/tests/test_engine.py` | Legacy index/count tests updated; new tests for many-to-one, identity, ranges, identical/unrelated/paraphrase, short documents. |
| `backend/tests/test_api.py` | API metrics bounded and consistent with the stored result; PDF shows the same index as the API. |

## 3. How it is calculated now

```
index = Σ (best cosine of each matched sentence in Document A, counted once)
        ─────────────────────────────────────────────────────────────────────
        number of comparable sentences in Document A
```

Every term ≤ 1.0 and there is at most one term per comparable sentence, so the index is bounded by
1.0 by construction — it stays a similarity/overlap indicator (`index = average matched similarity ×
coverage of A`), never a plagiarism percentage.

## 4. Verification (real runs, this sandbox)

Through the HTTP API, using the shipped sample documents plus synthetic pairs:

| Case | Index | Avg matched | Matched A | Evidence rows | Result |
| --- | --- | --- | --- | --- | --- |
| Identical PDFs | **100.0 %** (exactly) | 100.0 % | 28/28 | 28 | pass |
| Sample pair (paraphrase + verbatim) | **74.5 %** | 90.7 % | 23/28 | 23 | pass |
| Unrelated documents | **0.0 %** | 0.0 % | 0/6 | 0 | pass |
| Many-to-one (was 392.7 %) | **98.2 %** | 98.2 % | 5/5 | 20 | pass — no inflation |
| Too-short document | — | — | — | — | rejected `422 document_too_short` |
| JSON export vs stored result vs PDF | identical index (74.5 %) | — | — | — | pass |

- `pytest tests -q` → **89 passed**; `ruff check --select F,E9` clean; `npm run build` OK.
- Results page and `/history` render with no console errors; every percentage on the page is ≤ 100 %.
- Evaluation script unchanged: paraphrase threshold 0.62 → P 0.576 / R 0.731 / F1 0.644; the fix
  affects aggregation only, not pair-level classification.

## 5. GPU status

The device layer is untouched: `device = "cuda" if torch.cuda.is_available() else "cpu"`,
`all-MiniLM-L6-v2`, 384-d, single model instance, `inference_mode`, batch 16 on GPU / 32 on CPU,
OOM → halve → CPU. This sandbox has a CPU-only PyTorch build and no GPU, so every number above was
produced on CPU (`/api/health` → `device: cpu`, `cuda_available: false`, `gpu_name: null`). The
CUDA path could not be re-measured here and no GPU speed-up is claimed; run
`python backend/check_environment.py` and check `/api/health` on the target machine to confirm
`cuda`.

Note: stored analyses keep the metrics recorded when they were run. Re-run an older analysis to get
the corrected index.
