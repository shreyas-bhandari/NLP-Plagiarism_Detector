# VeriText AI — presentation script and viva guide

Everything here matches what the application actually does. Numbers quoted are the ones produced by
`backend/evaluation/evaluate.py` on the shipped 59-pair labelled set — say so when you quote them.

---

## 1. One-line pitch

> VeriText AI compares two academic documents using pretrained sentence embeddings, so it finds
> paraphrased overlap that string matching misses — and it shows the evidence for every flag instead
> of printing one "plagiarism percentage".

## 2. Six-minute demo script

| Time | What to do | What to say |
|---|---|---|
| 0:00 | Landing page | "Academic integrity, understood beyond words. The pipeline: extract → segment → encode → compare → classify." |
| 0:30 | Dashboard | "Everything here comes from the database — total analyses, documents processed, average time, average index. No placeholder numbers." |
| 1:00 | New analysis → upload `source_article.pdf` (A) and `student_submission.pdf` (B) | "PyMuPDF extracts text with page positions; the splitter is abbreviation-aware so 'et al.' doesn't cut a sentence; reference lists are excluded because they repeat across papers." |
| 1:45 | Click **Run semantic analysis** | "Both documents are encoded by all-MiniLM-L6-v2 — 384-dimensional unit vectors — and compared with cosine similarity in both directions." |
| 2:05 | Results: top metrics | "The similarity index is coverage-weighted: Σ best cosine of matched sentences ÷ comparable sentences. That's not a plagiarism percentage, and the page says so." |
| 2:30 | Distribution + classification | "8 exact, 4 near-exact, 11 semantic. Different evidence, counted separately. Note that the bars below the threshold are shown too." |
| 3:00 | Detected passages | "Consecutive matches are clustered: here's a passage of six sentences. Real reuse arrives in runs; boilerplate arrives as isolated hits." |
| 3:40 | Expand a match | "This is the point of the project: cosine 0.99, token Jaccard, sequence ratio, the shared terms, the 19-word verbatim run, and a caveat." |
| 4:05 | Point at the sidebar badge / `/api/health` | "The engine reports the device it is actually using — GPU on this laptop through CUDA, CPU otherwise. The same endpoint shows the PyTorch build, the GPU name and VRAM, and the batch size." |
| 4:20 | Side-by-side viewer | "Same colours in both panels, keyboard navigation, and headings/references shown greyed out because they weren't compared." |
| 5:00 | PDF report | "ReportLab document with methodology, thresholds, the match tables, limitations and the disclaimer." |
| 5:30 | Methodology page | "And here is what the evaluation actually measured — including that boilerplate scores higher than paraphrase. That's why one threshold can't be a verdict." |
| 5:50 | Future work | "Cross-encoder re-ranking, a reference corpus, section-aware weighting." |

## 3. Slide outline (8 slides)

1. **Problem** — string matching fails under rewriting; existing tools drown reviewers in boilerplate
   false positives.
2. **Objective** — semantic reuse detection with explainable evidence and honest limits.
3. **Architecture** — React SPA ↔ Flask REST ↔ services (extractor, preprocessor, embedding,
   similarity, detector, report) ↔ SQLite + TTL text store.
4. **NLP pipeline** — figures: sentence → tokens → 6-layer transformer → mean-pool → 384-d unit
   vector → cosine.
5. **Classification & safeguards** — exact / near-exact / semantic; reference exclusion, generic
   phrasing downgrade, citation-only suppression, passage clustering.
6. **Evaluation** — the category table and the three decision rules, with the honest conclusion.
7. **Interface** — dashboard, results with expanded evidence, side-by-side viewer, report.
8. **Limitations & future work** — no corpus search, heavy paraphrase weakness, small labelled set.

## 4. Viva questions with model answers

**Q: Why sentence embeddings instead of word matching?**
Word matching compares surface forms; a paraphrase shares meaning but few words. An embedding maps a
whole sentence to a point in a 384-dimensional space where paraphrases are close, so semantic overlap
survives synonym substitution and reordering.

**Q: What model, and why that one?**
`sentence-transformers/all-MiniLM-L6-v2`: a 6-layer MiniLM transformer distilled for sentence
similarity. It embeds a sentence in milliseconds, so it runs comfortably on a CPU and comfortably on
the 4 GB RTX 3050 when a CUDA-enabled PyTorch build is present — the same code path either way. It is
a standard, well-documented baseline. We load it once, reuse the same instance, and never fine-tune
it.

**Q: Explain the vector maths.**
The encoder mean-pools contextual token vectors into `v ∈ ℝ³⁸⁴`, then L2-normalises so `‖v‖ = 1`.
Cosine similarity is `(A·B)/(‖A‖‖B‖)`, which collapses to the dot product `A·B` for unit vectors —
exactly what the matrix product computes.

**Q: Why cosine and not Euclidean distance?**
Cosine compares direction (meaning) and ignores magnitude, which mainly encodes length/word count.
Normalised dot product also makes the whole comparison one matrix multiplication.

**Q: How do you avoid comparing every sentence pair?**
We do compare many pairs, but we never materialise the full matrix: we score in row blocks
(256 rows) and reduce each block to its top-3 candidates with `argpartition`, so memory stays
proportional to the block. Both directions are computed so coverage is fair for both documents.

**Q: What is the difference between exact, near-exact and semantic matches?**
Exact = identical after case/punctuation normalisation. Near-exact = token-sequence ratio ≥ 0.85
(a few words changed). Semantic = cosine ≥ 0.62 with different wording. They are separate evidence
types because they justify different conclusions.

**Q: Why not report a single "plagiarism percentage"?**
Because it would be misleading. Our own evaluation shows boilerplate sentences scoring 0.68–0.98
while genuine paraphrases score 0.26–0.68 — the number does not order evidence by seriousness. We
report a coverage-weighted similarity index, state its formula, and label it explicitly as not a
plagiarism percentage.

**Q: What are the false positives, and what do you do about them?**
In the evaluation the production rule produced 14 false positives at threshold 0.62 — almost all
generic academic phrasing ("Data were collected through semi-structured interviews") and textbook
definitions. Handling: reference lists and headings are excluded; pairs whose shared content words
are all generic are marked weak and suppressed below the high band; citation-only overlap is
suppressed; definition-shaped pairs are annotated; suppressed pairs remain visible with a reason.

**Q: And the false negatives?**
Seven pairs, all heavy paraphrases (cosine 0.26–0.59). That is a known limitation of MiniLM-scale
embeddings. Options: lower the threshold (more noise — the sweep shows precision collapsing), use a
cross-encoder for re-ranking, or fine-tune on a properly labelled corpus. We chose to expose the
sweep instead of hiding the trade-off.

**Q: How is coverage computed?**
Two ways: percentage of comparable sentences with at least one qualifying match, and percentage of
words inside matched sentences. Both are reported per document, because a submission can borrow from
a source without the reverse being true.

**Q: Why does one sentence matching several others not inflate the score?**
Counts are based on the best (primary) match per sentence. Extra candidates are stored as
`is_primary: false` alternatives for the reviewer and shown only when explicitly enabled.

**Q: How does the viewer know where to highlight?**
Extraction keeps paragraph indexes, page numbers and character offsets; segmentation keeps sentence
IDs and marks non-comparable sentences. The API returns both documents' sentence lists, and the UI
maps match sentence IDs to spans and colours.

**Q: What happens to uploaded documents?**
The upload is written to a private temp file, parsed, then deleted in a `finally` block. Extracted
text is cached in a TTL store (default 120 minutes) purely so the viewer can render it; deleting the
analysis removes it immediately. SQLite keeps metrics and short snippets, not documents.

**Q: How do you prevent someone uploading malware or a fake PDF?**
Extensions are allow-listed, sizes capped, and magic signatures verified; content is only parsed as
text by PyMuPDF/python-docx and never executed or rendered. Error messages never expose stack traces
or server paths. We do not claim a security audit — authentication, rate limiting and virus scanning
are explicitly listed as not implemented.

**Q: What is the database schema?**
`analyses` (one row per comparison: names, counts, metrics, options, full result JSON),
`matches` (per-pair rows with snippets, classification, score, explanation JSON),
`documents` (metadata only — file name, type, sizes, sha256). Indexed by analysis and creation date.

**Q: Why is the API synchronous?**
Two 600-word documents take ~0.21–0.32 s end to end on the CPU of the machine this was developed on.
A job queue would add infrastructure and failure modes without improving the user experience at this
scale; it is listed as future work for very large inputs.

**Q: How does the application decide between GPU and CPU?**
`services/hardware.py` resolves it once at startup: `device = "cuda" if torch.cuda.is_available() else "cpu"`,
and the SentenceTransformer is loaded onto that device. `VERITEXT_DEVICE` can force `cuda`, `cpu` or
`mps`. If a forced device is unavailable the engine degrades to CPU and records the reason — it never
pretends to be on the GPU.

**Q: Why a batch size of 16 on the GPU?**
The reference machine has a 4 GB RTX 3050 and the display/compositor shares that VRAM. 16 sentences of
MiniLM activations fit comfortably with headroom; larger batches gave no measurable benefit at this
document size and increase OOM risk. It is configurable per device (16 GPU / 32 CPU by default).

**Q: What happens if the GPU runs out of memory mid-analysis?**
The engine catches the OOM, empties the CUDA cache, halves the batch and retries the same sentences. If
a single sentence still does not fit, the model is moved to CPU for the rest of the session, the reason
is exposed as `fallback_reason`, and the analysis still completes. Only if that fallback is disabled
does the request fail — with a 503 and an actionable message, never with fake scores.

**Q: How do you know the reported hardware is real?**
Every field comes from `torch` and `platform` at runtime (`torch.cuda.get_device_name`,
`torch.cuda.mem_get_info`, `torch.version.cuda`, `sys.version`). The test suite asserts that when CUDA
is unavailable the GPU block is empty rather than invented, and `check_environment.py` prints the same
values so the two can be cross-checked.

**Q: Do you need the internet to run it?**
Only once, to download the model (~90 MB) into the Hugging Face cache. After that the model loads from
disk. If the first download fails, the backend reports `model_unavailable` with `error_kind
model_download_failed` and comparisons return HTTP 503 with an explanation — it does not silently
produce zeros or placeholder results. `VERITEXT_MODEL_LOCAL_ONLY=true` enforces cache-only operation.

**Q: Are the GPU and CPU results identical?**
The vectors are the same model with the same weights in float32; tiny differences from different
kernel implementations are possible but far below any threshold that matters (0.001-level). Because the
decisions are threshold-based, a pair sitting exactly on a boundary could in principle flip — which is
one more reason the interface reports evidence classes and passages instead of a single verdict.

**Q: Can the similarity index exceed 100%?**
No — and if it does, that is a bug, not a strong match. The index is
`Σ (best cosine of each matched sentence in Document A, counted once) ÷ comparable sentences in A`.
Every term is at most 1.0 and there is at most one term per comparable sentence, so the ratio is
bounded by 1.0 by construction. An earlier build summed *every* primary evidence row — including
reverse-only B→A rows, added to keep Document B's coverage complete — while dividing by A's sentence
count, so the ratio could pass 100% (392% on a many-to-one pair). The fix deduplicates the numerator
per A sentence; a clamp remains only as a floating-point guard.

**Q: Does "primary matches" count sentences or pairs?**
Sentences in Document A. `primary_matches` equals `coverage.A.sentences_matched`, so the headline
card, the coverage bar and the index all describe the same evidence set. The payload also exposes
`evidence_rows` (all qualifying pairs, including reverse-only rows that belong to B's coverage) — the
UI shows that as a secondary hint, not as the headline count.

**Q: What is the most interesting thing you learned?**
That similarity and misconduct are different axes. The embedding model is excellent at relatedness
(P 1.00, R 0.96 on the relatedness task) yet weak as a plagiarism classifier (F1 ≈ 0.64), because
boilerplate and definitions are semantically similar by design. The engineering work was therefore
mostly about evidence presentation and safeguards, not about improving the model.

**Q: If you had one more month?**
Cross-encoder re-ranking of the top 10 candidates per sentence (should raise paraphrase precision
substantially), a reference corpus behind a vector index, and a professionally labelled dataset with
inter-annotator agreement so the thresholds could be calibrated rather than chosen.

**Q: How would you scale this to thousands of submissions?**
Move analysis to a worker queue, keep embeddings cached by sentence hash, store vectors in an index
(FAISS/pgvector) over the reference corpus, then query top-k neighbours instead of pairwise
comparison; the detector and safeguards stay unchanged.

## 5. Common mistakes to avoid while presenting

- Do not call the similarity index "the plagiarism percentage".
- Do not claim a fixed accuracy figure; quote precision/recall *with* the dataset size and the
  positive/negative definition.
- Do not claim the tool searches the internet or a database of papers.
- Do not say "the model detects plagiarism" — it measures overlap; the reviewer decides.
- Do not claim a GPU speed-up you have not measured, and do not say the app "requires a GPU" — the CPU
  fallback is a first-class path.
- Do not quote precision/recall without saying they come from a 59-pair author-labelled set produced by
  `backend/evaluation/evaluate.py`.
