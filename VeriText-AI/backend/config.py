"""
Central configuration for the VeriText AI backend.

Every value can be overridden with an environment variable so that the same
codebase can run locally, in CI, or behind a real deployment without edits.
No credentials are hardcoded anywhere in this project.
"""

import os
from pathlib import Path


def _env_str(key: str, default: str) -> str:
    value = os.environ.get(key)
    return value.strip() if value is not None and value.strip() != "" else default


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


def _env_bool(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent


class Config:
    # ------------------------------------------------------------------- paths
    BASE_DIR = BASE_DIR
    PROJECT_ROOT = PROJECT_ROOT

    # ------------------------------------------------------------------ server
    HOST = _env_str("VERITEXT_HOST", "0.0.0.0")          # bind all interfaces (container friendly)
    PORT = _env_int("VERITEXT_PORT", 5000)
    DEBUG = _env_bool("VERITEXT_DEBUG", False)
    LOG_LEVEL = _env_str("VERITEXT_LOG_LEVEL", "INFO")

    # CORS: comma separated list of allowed origins. Default covers the Vite dev
    # server. The production build is served by Flask itself (same origin), so it
    # does not depend on CORS at all.
    CORS_ORIGINS = [
        o.strip()
        for o in _env_str(
            "VERITEXT_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173",
        ).split(",")
        if o.strip()
    ]

    # ---------------------------------------------------------------- uploads
    MAX_UPLOAD_MB = _env_int("VERITEXT_MAX_UPLOAD_MB", 25)
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024          # Flask enforced hard limit
    ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "md"}          # txt/md are handy for testing
    # Documents larger than this are rejected before the NLP stage: comparing
    # very large documents sentence-by-sentence becomes quadratic and slow.
    MAX_DOCUMENT_CHARS = _env_int("VERITEXT_MAX_DOCUMENT_CHARS", 400_000)   # ~65k words
    MAX_SENTENCES_PER_DOC = _env_int("VERITEXT_MAX_SENTENCES", 4000)

    # -------------------------------------------------------------- NLP model
    MODEL_NAME = _env_str("VERITEXT_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

    # --------------------------------------------------------------- hardware
    # Device selection happens at runtime (see services/hardware.py):
    #   "auto" -> CUDA when a working CUDA build + GPU are detected, CPU otherwise.
    # "cuda", "cpu" and "mps" can be forced. A forced device that is unavailable
    # degrades to CPU with an explicit note; it never silently fakes a result.
    DEVICE = _env_str("VERITEXT_DEVICE", "auto")

    # Batch size: 0 means "use the per-device default below". A 4 GB laptop GPU
    # (RTX 3050) is comfortable at 16; CPU batches can be larger because there is
    # no VRAM ceiling. Always overridable through VERITEXT_EMBED_BATCH.
    EMBEDDING_BATCH_SIZE = _env_int("VERITEXT_EMBED_BATCH", 0)
    EMBEDDING_BATCH_GPU = _env_int("VERITEXT_EMBED_BATCH_GPU", 16)
    EMBEDDING_BATCH_CPU = _env_int("VERITEXT_EMBED_BATCH_CPU", 32)
    EMBEDDING_CACHE_SIZE = _env_int("VERITEXT_EMBED_CACHE", 20_000)
    TORCH_THREADS = _env_int("VERITEXT_TORCH_THREADS", 4)      # used by CPU inference only

    # CUDA out-of-memory policy: halve the batch and retry, then (optionally) move
    # the model to CPU for the rest of the session rather than failing the analysis.
    CUDA_OOM_CPU_FALLBACK = _env_bool("VERITEXT_CUDA_FALLBACK_TO_CPU", True)
    EMBEDDING_WARMUP = _env_bool("VERITEXT_EMBED_WARMUP", True)

    # Model download behaviour. Offline installs (model already in the HF cache)
    # set this to true so a missing network connection cannot block startup.
    MODEL_LOCAL_ONLY = _env_bool("VERITEXT_MODEL_LOCAL_ONLY", False)

    # Row block used by the cosine search: peak memory stays O(BLOCK_ROWS x n_b)
    # instead of O(n_a x n_b), which matters on a shared GPU and on small VMs.
    SIMILARITY_BLOCK_ROWS = _env_int("VERITEXT_SIMILARITY_BLOCK_ROWS", 256)

    # ------------------------------------------------------- match thresholds
    # Calibrated empirically in backend/evaluation (see docs/evaluation_results.md).
    # They are CONFIGURABLE STARTING POINTS, not validated plagiarism boundaries.
    SEMANTIC_THRESHOLD = _env_float("VERITEXT_SEMANTIC_THRESHOLD", 0.62)
    HIGH_SIMILARITY = _env_float("VERITEXT_HIGH_SIMILARITY", 0.80)
    MODERATE_SIMILARITY = _env_float("VERITEXT_MODERATE_SIMILARITY", 0.65)
    NEAR_EXACT_LEXICAL = _env_float("VERITEXT_NEAR_EXACT_LEXICAL", 0.85)
    EXACT_LEXICAL = _env_float("VERITEXT_EXACT_LEXICAL", 0.99)

    # Matching controls
    TOP_K_PER_SENTENCE = _env_int("VERITEXT_TOP_K", 3)          # candidate matches kept per sentence
    MIN_SENTENCE_WORDS = _env_int("VERITEXT_MIN_SENTENCE_WORDS", 5)
    MIN_SENTENCE_CHARS = _env_int("VERITEXT_MIN_SENTENCE_CHARS", 25)
    PARAGRAPH_THRESHOLD = _env_float("VERITEXT_PARAGRAPH_THRESHOLD", 0.60)
    # Sentences whose only shared content words come from generic academic phrasing
    # are downgraded / suppressed so that boilerplate never reads as copying.
    SUPPRESS_COMMON_PHRASES = _env_bool("VERITEXT_SUPPRESS_COMMON", True)

    # -------------------------------------------------------------- storage
    STORAGE_DIR = Path(_env_str("VERITEXT_STORAGE_DIR", str(PROJECT_ROOT / "storage")))
    DATABASE_PATH = Path(_env_str("VERITEXT_DB_PATH", str(STORAGE_DIR / "veritext.sqlite3")))
    TEMP_UPLOAD_DIR = Path(_env_str("VERITEXT_TEMP_DIR", str(STORAGE_DIR / "tmp")))

    # Privacy: extracted document text is kept only in a short-lived session store
    # (in memory + optionally on disk) so that the comparison viewer can render it.
    # It is purged automatically after ANALYSIS_TEXT_TTL_MINUTES and immediately on
    # analysis deletion. Set SESSION_TEXT_TO_DISK=false for memory-only retention.
    SESSION_TEXT_TTL_MINUTES = _env_int("VERITEXT_TEXT_TTL_MINUTES", 120)
    SESSION_TEXT_TO_DISK = _env_bool("VERITEXT_TEXT_TO_DISK", True)
    # Persisted matches keep only short snippets (needed for history + reports).
    SNIPPET_MAX_CHARS = _env_int("VERITEXT_SNIPPET_CHARS", 600)
    RETAIN_SNIPPETS = _env_bool("VERITEXT_RETAIN_SNIPPETS", True)

    # ----------------------------------------------------------- pdf reports
    REPORT_TITLE = "VeriText AI — Semantic Similarity Analysis Report"
    REPORT_PRODUCT = "VeriText AI"
    REPORT_TAGLINE = "Beyond Matching Words. Understanding Meaning."
    ENGINE_VERSION = "veritext-engine-1.0"

    @classmethod
    def ensure_directories(cls) -> None:
        for directory in (cls.STORAGE_DIR, cls.TEMP_UPLOAD_DIR, cls.DATABASE_PATH.parent):
            directory.mkdir(parents=True, exist_ok=True)


Config.ensure_directories()
