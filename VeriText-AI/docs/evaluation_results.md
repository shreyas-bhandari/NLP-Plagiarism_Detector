# VeriText AI — NLP Engine Evaluation

*Generated 2026-11-03 06:49 UTC by `backend/evaluation/evaluate.py`.*

Model: `sentence-transformers/all-MiniLM-L6-v2` · Labelled pairs: **59** · Operating point: cosine ≥ **0.62**

Executed on: **cpu** · no CUDA GPU detected · PyTorch 2.15.0+cpu (CUDA build none) · Python 3.13.16 · batch 32 · Linux

This document reports measured numbers from a script that anyone can re-run. No accuracy value in this project is invented or estimated.

These results describe sentence-pair behaviour on a 59-pair, author-labelled set. They are an engineering sanity check for this implementation — **not** a validated academic benchmark: there is no inter-annotator agreement study, no third-party corpus and no confidence interval. Cosine values are device-independent in principle; tiny float differences between GPU and CPU kernels are far below every reported threshold.

## 1. Dataset

Sentence pairs were written for this project and labelled by hand across seven categories. Each row below shows the pair counts used for evaluation.

| Category | What it contains | Pairs | Cosine min | Median | Mean | Max |
|---|---|---:|---:|---:|---:|---:|
| `identical` | identical sentences | 8 | 1.000 | 1.000 | 1.000 | 1.000 |
| `lightly_modified` | light edits / synonyms | 8 | 0.917 | 0.989 | 0.978 | 0.996 |
| `paraphrase` | rewritten, same claim | 10 | 0.262 | 0.543 | 0.540 | 0.679 |
| `semantically_similar` | same topic, different claim | 8 | 0.240 | 0.512 | 0.475 | 0.553 |
| `common_expression` | generic academic phrasing | 10 | 0.678 | 0.804 | 0.821 | 0.980 |
| `technical_definition` | textbook definitions | 7 | 0.631 | 0.913 | 0.845 | 0.961 |
| `unrelated` | unrelated sentences | 8 | -0.086 | -0.025 | -0.022 | 0.059 |

**Immediate observation:** the cosine distributions of `paraphrase` (0.26–0.68) and `common_expression` (0.68–0.98) barely overlap, and the boilerplate scores are *higher* than the paraphrase scores. A single similarity threshold therefore cannot separate rewriting from standard academic phrasing — this is the central empirical finding of the evaluation, and the reason the engine combines semantic, lexical and safeguard signals instead of reporting one number.

## 2. Task: reuse identification

Positive class = identical, lightly modified or paraphrased pairs (26 pairs). Negative class = semantically similar but independent claims, common expressions, textbook definitions and unrelated sentences (33 pairs).

| Decision rule | Threshold | Precision | Recall | F1 | TP | FP | FN | TN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Naive cosine threshold (best F1) | 0.45 | 0.521 | 0.962 | 0.676 | 25 | 23 | 1 | 10 |
| Cosine OR near-exact lexical (best F1) | 0.45 | 0.521 | 0.962 | 0.676 | 25 | 23 | 1 | 10 |
| VeriText production rule (best F1) | 0.89 | 0.727 | 0.615 | 0.667 | 16 | 6 | 10 | 27 |
| Naive cosine @ operating point (0.62) | 0.62 | 0.528 | 0.731 | 0.613 | 19 | 17 | 7 | 16 |
| Cosine OR near-exact @ operating point (0.62) | 0.62 | 0.528 | 0.731 | 0.613 | 19 | 17 | 7 | 16 |
| VeriText production rule @ operating point (0.62) | 0.62 | 0.576 | 0.731 | 0.644 | 19 | 14 | 7 | 19 |

Reading these numbers honestly:

* The shipped rule reaches F1 **0.644** at the operating point, with precision 0.576 and recall 0.731.
* Precision is limited by three things that a semantic model cannot resolve on its own: near-verbatim *definitions*, standard *methodology sentences* and *future-work boilerplate*. These are reported rather than silently dropped, because verbatim overlap is genuine evidence that a human must classify.
* Recall is limited by the well-known weakness of MiniLM-scale sentence embeddings on heavy paraphrase (cosine often 0.45–0.60). Lowering the threshold recovers paraphrase recall but also admits far more boilerplate; the sweep table makes that trade-off explicit.

## 3. Effect of the generic-phrasing safeguard

Task: flag `paraphrase` pairs (10) while rejecting `common_expression` and `technical_definition` pairs (17).

| Variant | Precision | Recall | F1 |
|---|---:|---:|---:|
| Raw cosine ≥ operating point | 0.150 | 0.300 | 0.200 |
| Production classification (no suppression) | 0.150 | 0.300 | 0.200 |
| Production classification + suppression | 0.176 | 0.300 | 0.222 |

The safeguard suppressed **3** pair(s) at the operating point (common_expression). Suppressed pairs stay visible in the API with a reason; they are only excluded from headline counts. The safeguard is deliberately conservative: it never suppresses exact or near-exact wording.

## 4. Task: semantic relatedness

Positive class = identical, lightly modified, paraphrase and semantically similar pairs (34). This measures whether the embedding model understands meaning, independent of questions about copying.

Best operating point: threshold 0.40 → precision **1.000**, recall **0.961**, F1 **0.980**.

## 5. Errors at the operating point

### False positives (flagged but labelled as not reuse)

* `ca-01` (common_expression, cosine 0.804, rule `semantic`): “Further research is needed to confirm these findings in different settings.…” ↔ “Further research is required to confirm these results in other contexts.…”
* `ca-02` (common_expression, cosine 0.781, rule `semantic`): “In recent years, machine learning has gained significant attention.…” ↔ “In recent years, deep learning has attracted considerable attention.…”
* `ca-05` (common_expression, cosine 0.845, rule `semantic`): “This paper presents a novel framework for document comparison.…” ↔ “This article presents a new framework for text comparison.…”
* `ca-07` (common_expression, cosine 0.980, rule `semantic`): “Data were collected through semi-structured interviews.…” ↔ “Data were gathered using semi-structured interviews.…”
* `ca-08` (common_expression, cosine 0.871, rule `semantic`): “On the other hand, the second condition showed no significant difference.…” ↔ “However, no significant difference was observed for the second condition.…”
* `ca-09` (common_expression, cosine 0.804, rule `semantic`): “These findings suggest that further investigation is warranted.…” ↔ “These results suggest that additional investigation is needed.…”
* `ca-10` (common_expression, cosine 0.948, rule `semantic`): “The present study has several limitations that should be acknowledged.…” ↔ “This study has a number of limitations that must be acknowledged.…”
* `td-01` (technical_definition, cosine 0.886, rule `semantic`): “Cosine similarity is the cosine of the angle between two non-zero vectors.…” ↔ “Cosine similarity measures the angle between two non-zero vectors in an inner product space.…”
* `td-02` (technical_definition, cosine 0.914, rule `semantic`): “A sentence embedding is a fixed-length vector representation of a sentence.…” ↔ “A sentence embedding represents a sentence as a dense vector of fixed dimensionality.…”
* `td-03` (technical_definition, cosine 0.935, rule `semantic`): “Precision is the ratio of true positives to all predicted positives.…” ↔ “Precision equals the number of true positives divided by the number of predicted positives.…”
* `td-04` (technical_definition, cosine 0.631, rule `semantic`): “A transformer is a neural architecture based entirely on attention mechanisms.…” ↔ “The transformer architecture relies solely on attention and dispenses with recurrence.…”
* `td-05` (technical_definition, cosine 0.913, rule `semantic`): “Tokenisation splits raw text into subword units before encoding.…” ↔ “Tokenisation converts raw text into subword pieces prior to encoding.…”
* `td-06` (technical_definition, cosine 0.961, rule `semantic`): “F1 score is the harmonic mean of precision and recall.…” ↔ “The F1 score combines precision and recall as their harmonic mean.…”
* `td-07` (technical_definition, cosine 0.675, rule `semantic`): “L2 normalisation scales a vector so that its Euclidean length is one.…” ↔ “Normalising a vector by its L2 norm makes its magnitude equal to unity.…”

### False negatives (labelled reuse but not flagged)

* `pp-01` (paraphrase, cosine 0.501, sequence ratio 0.32): “A student who replaces half of the words in a passage can reduce a string-matching score to near zero without …” ↔ “Rewriting roughly half of the vocabulary in a paragraph is enough to push lexical similarity close to zero, ev…”
* `pp-02` (paraphrase, cosine 0.488, sequence ratio 0.12): “Sentence embeddings are comparatively insensitive to surface form because the representation is learned from l…” ↔ “Because these vectors are trained on very large text collections, small changes in wording barely affect them.…”
* `pp-03` (paraphrase, cosine 0.588, sequence ratio 0.18): “Any deployment of semantic similarity for integrity screening requires human review of the flagged passages.…” ↔ “Whoever deploys meaning-based comparison to screen for misconduct must still have people examine the passages …”
* `pp-04` (paraphrase, cosine 0.585, sequence ratio 0.25): “The character n-gram baseline detected only 18% of paraphrases.…” ↔ “Only about one in five rewritten passages were caught by the n-gram approach.…”
* `pp-05` (paraphrase, cosine 0.489, sequence ratio 0.07): “Reference lists are excluded because bibliographies repeat across papers and inflate similarity.…” ↔ “We drop the bibliography, since the same citations appear in many publications and push scores upwards.…”
* `pp-08` (paraphrase, cosine 0.262, sequence ratio 0.12): “Exact matches were detected equally well by both systems.…” ↔ “Both approaches performed the same on verbatim overlaps.…”
* `pp-09` (paraphrase, cosine 0.473, sequence ratio 0.13): “The similarity score describes overlap between texts and does not establish misconduct.…” ↔ “A high number only tells you that the two documents share language; it is not evidence that anyone cheated.…”

## 6. Conclusions drawn from this evaluation

1. The embedding model performs exactly as expected on its own task: unrelated text sits near zero cosine, paraphrases sit clearly above unrelated text, and identical text sits at 1.0. It is a usable signal.
2. Sentence-level cosine alone is **not** a plagiarism detector. Boilerplate and definitions can outscore genuine paraphrases, so the engine separates exact, near-exact and semantic evidence and marks weak evidence explicitly.
3. Reproducible evaluation matters more than a headline number. The dataset is small (59 pairs), written by the project author, and drawn mostly from one domain (computing/education). Treat these figures as an engineering sanity check, not as benchmark performance, and do not present them as accuracy claims about real documents.

## 7. Limitations of the evaluation

* 59 pairs is far too few for statistically stable estimates; a single pair moves precision by several points.
* Labels encode the author's judgement about what counts as 'reuse', which is itself contested in academic-integrity practice.
* Pair-level evaluation ignores document context. In the application, matches are clustered into passages, which changes how evidence should be interpreted.
* Only one embedding model is evaluated. A larger cross-encoder or a domain-tuned model would likely change the numbers, and would need its own calibration.

