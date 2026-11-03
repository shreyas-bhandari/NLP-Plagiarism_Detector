# VeriText AI — API reference

Base URL: `http://localhost:5000` (or the Vite dev proxy at `http://localhost:5173`, which forwards
`/api/*` to Flask).

The examples use `curl`; on Windows PowerShell the equivalent is `Invoke-RestMethod`
(e.g. `Invoke-RestMethod http://localhost:5000/api/health | ConvertTo-Json -Depth 6`).
`GET /api/health` also works in a browser.

All endpoints return JSON except the PDF report. Every response uses one of two envelopes:

```json
{ "success": true, "message": "optional", "data": { } }
```

```json
{ "success": false, "error": { "code": "invalid_request", "message": "…", "hint": "optional" } }
```

Common HTTP status codes: `200` OK, `201` created, `400` invalid request, `404` not found,
`410` resource expired (session text or document cache), `413` too large, `415` unsupported media type,
`422` unprocessable document, `500` internal error, `503` model unavailable.

---

## GET /api/health

Service, model and hardware status. Every value is read from the running process — Python version,
PyTorch version, whether that wheel contains CUDA, CUDA availability, GPU name and VRAM, the resolved
inference device and the effective embedding batch size. Nothing is assumed or fabricated: on a
CPU-only machine `device` is `"cpu"`, `gpu_name` is `null` and `runtime.notes` explains why.

`status` is `ok` when the model is loaded, `loading` while it is being loaded, and
`model_unavailable` when it could not be loaded (for example the first-run download failed).

```json
{
  "success": true,
  "data": {
    "status": "ok",
    "service": "VeriText AI backend",
    "version": "veritext-engine-1.0",
    "time": "2026-11-02T10:15:00+00:00",
    "model": {
      "model": "sentence-transformers/all-MiniLM-L6-v2",
      "loaded": true,
      "dimension": 384,
      "load_seconds": 0.53,
      "error": null,
      "error_kind": null,
      "device": "cuda",
      "device_requested": "auto",
      "cuda_available": true,
      "gpu_name": "NVIDIA GeForce RTX 3050 Laptop GPU",
      "gpu_total_vram_mb": 4096,
      "torch_version": "2.4.1+cu124",
      "cuda_version": "12.4",
      "batch_size": 16,
      "fallback_reason": null,
      "oom_events": 0,
      "oom_retries": 0,
      "framework": "PyTorch 2.4.1+cu124 (cuda)",
      "cache_entries": 118,
      "encode_calls": 4,
      "sentences_encoded": 174,
      "normalised": true,
      "local_files_only": false,
      "load_attempts": 1
    },
    "runtime": {
      "python": { "version": "3.11.9", "implementation": "CPython", "supported": true,
                  "recommended": "3.11 or 3.12 (3.10+ required)" },
      "torch": { "available": true, "version": "2.4.1+cu124", "cuda_build": "12.4",
                 "cudnn_version": 90100, "threads": 4, "error": null },
      "cuda": { "available": true, "device_count": 1, "version": "12.4" },
      "device": { "requested": "auto", "resolved": "cuda", "type": "cuda",
                  "name": "NVIDIA GeForce RTX 3050 Laptop GPU", "inference_on_gpu": true },
      "gpu": { "name": "NVIDIA GeForce RTX 3050 Laptop GPU", "index": 0,
               "total_vram_mb": 4096, "free_vram_mb": 3271, "compute_capability": "8.6" },
      "batch": { "effective": 16, "gpu_default": 16, "cpu_default": 32, "override": null },
      "platform": { "system": "Windows", "release": "10", "machine": "AMD64" },
      "notes": []
    },
    "storage": {
      "session_documents_in_memory": 3,
      "session_documents_on_disk": 3,
      "retention_minutes": 120,
      "disk_retention_enabled": true
    },
    "limits": { "max_upload_mb": 25, "max_document_chars": 400000,
                "max_sentences_per_document": 4000,
                "allowed_extensions": ["docx", "md", "pdf", "txt"] },
    "thresholds": { "semantic_min": 0.62, "high": 0.8, "moderate": 0.65 }
  }
}
```

Notes on the fields that matter when something goes wrong:

| Field | Meaning |
|---|---|
| `model.device` | Device inference actually runs on: `cuda`, `cpu` or `mps` |
| `model.fallback_reason` | Set when a CUDA OOM moved the session to CPU (explains the downgrade) |
| `model.error_kind` | `model_download_failed` (no network / not cached) or `model_load_failed` |
| `runtime.notes` | Human-readable reasons, e.g. "This PyTorch build was installed without CUDA…" |
| `model.batch_size` | Effective embedding batch (16 on GPU, 32 on CPU unless overridden) |
| `model.oom_events` / `oom_retries` | Out-of-memory events handled since startup |

## POST /api/documents/upload

Upload and parse one document. The file is deleted from disk immediately after extraction; the
parsed structure is cached for `SESSION_TEXT_TTL_MINUTES` so the comparison step does not need a
second upload.

**Content type:** `multipart/form-data`

| Field | Required | Notes |
|---|---|---|
| `file` | yes | PDF, DOCX, TXT or MD; ≤ 25 MB (configurable) |
| `label` | no | `A` or `B` (display only, default `A`) |
| `exclude_references` | no | `true`/`false`, default `true` |
| `ignore_quotations` | no | `true`/`false`, default `false` |

**201 Created**

```json
{
  "success": true,
  "data": {
    "document_id": "doc_1679c8dedc734ffa",
    "label": "A",
    "filename": "source_article.pdf",
    "file_type": "pdf",
    "word_count": 573,
    "char_count": 4137,
    "page_count": 2,
    "paragraph_count": 21,
    "sentence_count": 53,
    "eligible_sentence_count": 28,
    "sections_present": ["body", "references"],
    "warnings": ["Document A: 8 sentence(s) from the reference list were excluded …"],
    "preview": { "excerpt": "Semantic Representations for …", "paragraph_count": 21,
                 "first_paragraphs": [ { "index": 0, "page": 1, "text": "…" } ] },
    "processing_ms": 14,
    "retention_minutes": 120
  }
}
```

Errors: `invalid_upload` (400/413/415), `pdf_open_failed` / `docx_open_failed` (422),
`scanned_pdf` (422, with an OCR hint), `document_too_short` (422), `document_too_large` (413),
`too_many_sentences` (413).

---

## GET /api/documents/{document_id}

Metadata and preview for a still-cached upload. `410 document_expired` when the TTL has passed.

## DELETE /api/documents/{document_id}

Removes a cached upload immediately (privacy control). `404` if unknown.

---

## POST /api/analysis/compare

Runs the full comparison. Two input styles:

**A. JSON (documents already uploaded)**

```json
{
  "doc_a_id": "doc_…",
  "doc_b_id": "doc_…",
  "options": {
    "exclude_references": true,
    "exclude_headings": true,
    "ignore_quotations": false,
    "semantic_threshold": 0.62,
    "paragraph_threshold": 0.60,
    "top_k": 3,
    "min_sentence_words": 5
  }
}
```

**B. multipart** — fields `file_a`, `file_b` and an optional JSON string `options`.

Option ranges are validated server-side (`semantic_threshold` 0.30–0.99, `top_k` 1–5,
`min_sentence_words` 3–40). Out-of-range values return `400`.

If the embedding model is not available — the first-run download could not reach Hugging Face, or CUDA
ran out of memory with the CPU fallback disabled — the endpoint returns **503** with an actionable
message. It never returns placeholder or fabricated scores:

```json
{ "success": false,
  "error": {
    "code": "embedding_unavailable",
    "message": "The pretrained model is not in the local Hugging Face cache and could not be downloaded …",
    "hint": "Run `python check_environment.py` in the backend folder, or check GET /api/health …"
  } }
```

**201 Created** (abridged; the full object is described below)

```json
{
  "success": true,
  "data": {
    "analysis_id": "an_5c8f86bcab304a6c",
    "created_at": "2026-11-02T12:28:51+00:00",
    "status": "completed",
    "summary": { "weighted_similarity": 0.745, "primary_matches": 23, "…": "…" },
    "matches": [ { "id": "M1", "…": "…" } ],
    "documents": { "A": { }, "B": { } },
    "engine": { "model": "…", "device": "cuda", "batch_size": 16, "timings": { } },
    "warnings": [],
    "disclaimer": "Similarity is measured, misconduct is not. …",
    "session_text_available": true,
    "retention_minutes": 120,
    "request_ms": 233
  }
}
```

### Result object

| Key | Meaning |
|---|---|
| `summary.weighted_similarity` | Coverage-weighted index = Σ(best cosine per matched sentence in A, each counted once) ÷ comparable sentences in A. Always 0–1 |
| `summary.average_matched_similarity` | Mean of each matched sentence's best cosine in Document A (one contribution per sentence) |
| `summary.max_similarity` | Highest single sentence similarity (any evidence pair) |
| `summary.primary_matches` | Matched sentences in Document A — the evidence the headline metrics use |
| `summary.evidence_rows` | Qualifying evidence pairs, including reverse-only (B→A) rows that feed Document B's coverage |
| `summary.reverse_only_evidence` | Count of those reverse-only rows (never added to the index) |
| `summary.exact_matches` / `near_exact_matches` / `semantic_matches` | Counts by classification (primary, non-suppressed) |
| `summary.paraphrase_matches` | Semantic matches with low lexical overlap |
| `summary.suppressed_matches` | Low-evidence matches excluded from headline counts |
| `summary.generic_phrasing_matches` | Matches flagged as generic academic phrasing |
| `summary.passages_detected` / `largest_passage_sentences` | Passage clustering results |
| `summary.coverage.A/B` | `sentences_considered`, `sentences_matched`, `sentence_coverage_pct`, `words_considered`, `words_covered`, `word_coverage_pct` |
| `summary.band` | `level` (`low`/`moderate`/`elevated`/`high`), `label`, `description` |
| `summary.distribution` | Histogram of best-match scores per comparable sentence in A |
| `summary.explanation_of_weighted_index` | Plain-language definition of the index |
| `matches[]` | All candidates, primary and secondary (see below) |
| `paragraph_matches[]` | Paragraph-level similarities (mean-pooled sentence vectors) |
| `passages[]` | Clusters with `size`, `source_span`, `target_span`, `similarity_max`, `classification` |
| `many_to_one_groups[]` | One source sentence matched by several targets |
| `documents.A/B` | File name, type, pages, words, sentences, sections |
| `engine` | Model, dimension, thresholds, options, **device + batch size actually used**, timings (embedding / matching / total) |
| `warnings[]` | Processing notes (exclusions, short documents, large inputs) |

### Match object

```json
{
  "id": "M1",
  "is_primary": true,
  "rank_in_source": 1,
  "classification": "near_exact",
  "classification_label": "Near-exact textual match",
  "subtype": null,
  "similarity": 0.99,
  "similarity_pct": 99.0,
  "band": "very_high",
  "band_label": "Very high semantic similarity (90-100%)",
  "source": { "sentence_id": "A-18", "index": 18, "text": "…", "page": 1,
              "paragraph": 4, "section": "body", "word_count": 24, "start": 812, "end": 964 },
  "target": { "sentence_id": "B-11", "index": 11, "text": "…", "…": "…" },
  "signals": {
    "cosine": 0.99, "sequence_ratio": 0.94, "token_jaccard": 0.78,
    "content_overlap": 0.82,
    "shared_content_terms": ["bibliographies", "excluded", "matching"],
    "shared_token_count": 17, "longest_verbatim_words": 19
  },
  "explanation": {
    "headline": "Almost identical wording: 94% of the token sequence matches …",
    "reasons": ["19 consecutive words are identical verbatim.", "…"],
    "shared_terms": ["bibliographies", "excluded", "matching"],
    "verbatim_run": "reference lists are excluded from matching because bibliographies repeat",
    "verbatim_words": 19,
    "definition_like": false,
    "caveat": "This flag describes textual/semantic overlap only. …"
  },
  "suppressed": false,
  "suppress_reason": null,
  "generic_phrasing": false,
  "generic_ratio": 0.12,
  "evidence_strength": "strong",
  "cluster": { "cluster_id": "PS3", "size": 4, "similarity_max": 0.99 },
  "mutual_best": true
}
```

`suppress_reason` is one of `generic_academic_phrasing`, `no_shared_content_terms`,
`citation_context_only`, or `null`. `evidence_strength` is `strong`, `moderate` or `weak`.

---

## GET /api/analysis/{analysis_id}

Returns the stored result in the same shape as the compare response (plus
`session_text_available`). For a failed analysis, `status` is `"failed"` with `error_message`.

## GET /api/analysis/{analysis_id}/documents

Segmented text for the comparison viewer.

```json
{ "success": true,
  "data": { "analysis_id": "an_…", "A": { "sentences": [ … ], "paragraphs": [ … ] },
            "B": { … }, "retention_minutes": 120 } }
```

Each sentence carries `id`, `index`, `text`, `page`, `paragraph`, `section`, `eligible`,
`exclude_reason`, `word_count`. `410 document_text_expired` once the TTL has passed — scores and the
report remain available.

## GET /api/analysis/{analysis_id}/report

Generates the PDF on demand and returns it as an attachment
(`Content-Type: application/pdf`, `Cache-Control: no-store`).

## GET /api/analysis/{analysis_id}/export

Returns the raw result JSON as a download (reproducible research / notebooks).

## DELETE /api/analysis/{analysis_id}

Deletes the analysis, its match rows and any retained document text. `404` if unknown.

## GET /api/analysis/history

`?limit=20&offset=0&search=student`

```json
{ "success": true,
  "data": { "items": [ { "id": "an_…", "created_at": "…", "status": "completed",
                         "doc_a_name": "source_article.pdf", "doc_b_name": "student_submission.pdf",
                         "weighted_similarity": 0.745, "primary_matches": 23,
                         "duration_ms": 233, "summary": { "…": "…" } } ],
            "total": 12, "limit": 20, "offset": 0 } }
```

## GET /api/stats/dashboard

```json
{ "success": true,
  "data": { "total_analyses": 12, "completed_analyses": 12, "failed_analyses": 0,
            "documents_processed": 24, "average_duration_ms": 233,
            "average_weighted_similarity_pct": 74.5,
            "total_exact_matches": 96, "total_near_exact_matches": 48,
            "total_semantic_matches": 132,
            "recent": [ … ], "activity": [ { "day": "2026-11-02", "analyses": 2,
                                             "avg_similarity": 0.7447 } ],
            "engine": { "model": "sentence-transformers/all-MiniLM-L6-v2", "ready": true } } }
```

All values are computed from SQLite rows; an empty database returns zeros, never placeholder numbers.

---

## Configuration reference

Every setting is environment-overridable (see `backend/config.py`):

| Variable | Default | Purpose |
|---|---|---|
| `VERITEXT_HOST` / `VERITEXT_PORT` | `0.0.0.0` / `5000` | Bind address |
| `VERITEXT_CORS_ORIGINS` | Vite dev origins | Comma-separated allowed origins |
| `VERITEXT_MAX_UPLOAD_MB` | `25` | Upload size limit |
| `VERITEXT_MAX_DOCUMENT_CHARS` | `400000` | Extracted-text limit |
| `VERITEXT_MAX_SENTENCES` | `4000` | Sentences per document |
| `VERITEXT_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model |
| `VERITEXT_DEVICE` | `auto` | `auto` \| `cuda` \| `cpu` \| `mps` — resolved device is reported by `/api/health` |
| `VERITEXT_EMBED_BATCH` | `0` | Explicit batch size for both devices (`0` = use the per-device defaults) |
| `VERITEXT_EMBED_BATCH_GPU` | `16` | GPU batch size (kept small for a 4 GB RTX 3050) |
| `VERITEXT_EMBED_BATCH_CPU` | `32` | CPU batch size |
| `VERITEXT_EMBED_WARMUP` | `true` | Encode two warm-up sentences at startup |
| `VERITEXT_CUDA_FALLBACK_TO_CPU` | `true` | After a CUDA OOM, continue on CPU instead of failing |
| `VERITEXT_MODEL_LOCAL_ONLY` | `false` | Never contact Hugging Face; require the local cache |
| `VERITEXT_TORCH_THREADS` | `4` | CPU inference threads |
| `VERITEXT_SIMILARITY_BLOCK_ROWS` | `256` | Row block of the cosine search (bounds peak memory) |
| `VERITEXT_SEMANTIC_THRESHOLD` | `0.62` | Cosine threshold for semantic matches |
| `VERITEXT_HIGH_SIMILARITY` / `VERITEXT_MODERATE_SIMILARITY` | `0.80` / `0.65` | Display bands |
| `VERITEXT_NEAR_EXACT_LEXICAL` | `0.85` | Token-sequence ratio for near-exact |
| `VERITEXT_TOP_K` | `3` | Candidate matches per sentence |
| `VERITEXT_STORAGE_DIR` / `VERITEXT_DB_PATH` | `storage/` | Database and temp files |
| `VERITEXT_TEXT_TTL_MINUTES` | `120` | Extracted-text retention (`0` = keep nothing) |
| `VERITEXT_TEXT_TO_DISK` | `true` | Memory-only retention if `false` |
| `VERITEXT_RETAIN_SNIPPETS` | `true` | Store short excerpts with matches |
| `VERITEXT_LOG_LEVEL` | `INFO` | Logging verbosity |
