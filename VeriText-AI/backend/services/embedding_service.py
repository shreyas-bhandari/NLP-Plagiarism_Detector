"""
Sentence-embedding service.

What happens here (and why it is the heart of VeriText AI)
----------------------------------------------------------
A transformer encoder (``sentence-transformers/all-MiniLM-L6-v2``) is loaded
**once** per process and reused for every request. For each sentence it runs a
forward pass over the token sequence and mean-pools the contextual token
vectors into a single 384-dimensional vector:

    sentence text  ->  [CLS] tok1 tok2 ... tokN [SEP]  ->  encoder (6 layers)
                   ->  token vectors (N x 384)
                   ->  mean pooling over real tokens
                   ->  dense vector v (384 numbers)
                   ->  L2 normalisation  ||v|| = 1

Two sentences that mean similar things land close together in that 384-d space.
Because vectors are L2-normalised, the cosine similarity of two sentences is
simply their dot product (see :mod:`services.similarity_engine`).

Nothing here is hardcoded, simulated or randomised: the vectors come from the
real pretrained network running on the uploaded text. The model is *not* trained
or fine-tuned by this project.

Device policy
-------------
The device is resolved by :mod:`services.hardware` — CUDA when a CUDA-enabled
PyTorch build can actually see a GPU, CPU otherwise. A 4 GB laptop GPU cannot
hold large activation batches, so inference runs in batches (16 by default on
GPU, overridable), inside ``torch.inference_mode()``, with no gradient tracking.
If CUDA runs out of memory the batch is halved and the step retried; if even a
single sentence does not fit, the model is moved to CPU for the rest of the
session instead of failing the analysis. Every one of those events is reported
through :meth:`EmbeddingService.status`.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections import OrderedDict
from typing import Dict, List, Optional, Sequence

import numpy as np

from config import Config
from services import hardware

logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    """Raised when the embedding model is unavailable or fails."""


def _model_key(text: str) -> str:
    """Stable cache key for a sentence (sha1 of its exact text)."""
    return hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()


def _looks_like_oom(exc: BaseException) -> bool:
    """True when an exception is a CUDA/HIP out-of-memory condition."""
    name = type(exc).__name__.lower()
    if "outofmemory" in name:
        return True
    message = str(exc).lower()
    needles = (
        "out of memory",
        "cuda error: out of memory",
        "cublas_status_alloc_failed",
        "cudnn_status_alloc_failed",
        "unable to allocate",
        "hip error: out of memory",
    )
    return any(needle in message for needle in needles)


def _looks_like_offline_error(exc: BaseException) -> bool:
    """True when a model load failure looks like a network / cache problem."""
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    if name in {"localentrynotfounderror", "connectionerror", "connecttimeout", "readtimeout"}:
        return True
    markers = (
        "couldn't connect",
        "could not connect",
        "connection error",
        "connectionerror",
        "offline mode is enabled",
        "we couldn't connect to",
        "max retries exceeded",
        "failed to establish a new connection",
        "temporary failure in name resolution",
        "no address associated with hostname",
        "proxyerror",
        "sslerror",
        "localentrynotfounderror",
        "is not a local folder and is not a valid model identifier",
    )
    return any(marker in message for marker in markers)


class EmbeddingService:
    """Thread-safe singleton wrapper around a SentenceTransformer model."""

    _instance: Optional["EmbeddingService"] = None
    _instance_lock = threading.Lock()

    def __init__(self, model_name: str = Config.MODEL_NAME):
        self.model_name = model_name
        self._model = None
        self._load_error: Optional[str] = None
        self._load_error_kind: Optional[str] = None
        self._model_lock = threading.Lock()
        self._cache: "OrderedDict[str, np.ndarray]" = OrderedDict()
        self._cache_lock = threading.Lock()
        self._load_seconds: Optional[float] = None
        self._encode_calls = 0
        self._encode_sentences = 0

        # device / memory state
        self._device: Optional[str] = None
        self._batch_size: Optional[int] = None
        self._fallback_reason: Optional[str] = None
        self._oom_events = 0
        self._oom_retries = 0
        self._load_attempts = 0

    # ------------------------------------------------------------------ setup
    @classmethod
    def instance(cls) -> "EmbeddingService":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = EmbeddingService()
        return cls._instance

    @property
    def device(self) -> str:
        return self._device or hardware.resolved_device()

    @property
    def batch_size(self) -> int:
        if self._batch_size:
            return self._batch_size
        return hardware.resolve_batch_size(self.device)

    def load(self, blocking: bool = True) -> bool:
        """Load the transformer. Returns True on success; never raises by default.

        Loading is idempotent: after the first successful call the same model
        instance is reused for every request, so the weights are never downloaded
        or deserialised twice.
        """
        if self._model is not None:
            return True
        with self._model_lock:
            if self._model is not None:
                return True
            self._load_attempts += 1
            try:
                import torch
                from sentence_transformers import SentenceTransformer

                torch.set_num_threads(max(1, Config.TORCH_THREADS))
                torch.set_grad_enabled(False)          # inference only, no autograd graph

                target = hardware.resolved_device()
                requested_local_only = Config.MODEL_LOCAL_ONLY
                hardware.log_startup_report()

                started = time.perf_counter()
                if target == "cuda":
                    logger.info(
                        "Loading %s on GPU (CUDA) — first run downloads ~90 MB from Hugging Face",
                        self.model_name,
                    )
                else:
                    logger.info(
                        "Loading %s on CPU — first run downloads ~90 MB from Hugging Face",
                        self.model_name,
                    )

                try:
                    self._model = SentenceTransformer(
                        self.model_name,
                        device=target,
                        local_files_only=requested_local_only,
                    )
                except TypeError:
                    # Older sentence-transformers releases do not accept local_files_only.
                    self._model = SentenceTransformer(self.model_name, device=target)

                self._model.eval()
                self._device = target
                self._batch_size = hardware.resolve_batch_size(target)
                self._load_seconds = round(time.perf_counter() - started, 2)
                self._load_error = None
                self._load_error_kind = None

                logger.info(
                    "Model ready in %.2fs on %s (dim=%s, batch=%s, max_seq_len=%s)",
                    self._load_seconds,
                    self.device,
                    self.dimension,
                    self.batch_size,
                    getattr(self._model, "max_seq_length", "?"),
                )
                if Config.EMBEDDING_WARMUP:
                    self._warmup()
                return True
            except Exception as exc:  # pragma: no cover - depends on environment
                self._model = None
                self._register_load_error(exc, blocking)
                return False

    def _register_load_error(self, exc: BaseException, blocking: bool) -> None:
        self._load_error = f"{type(exc).__name__}: {exc}"
        if _looks_like_offline_error(exc):
            self._load_error_kind = "model_download_failed"
            logger.error(
                "Could not obtain the embedding model %s. The model has to be downloaded once "
                "from Hugging Face; the local cache (%s) does not contain it and the network "
                "request failed. Connect to the internet for the first run, or pre-download the "
                "model, or set VERITEXT_MODEL_LOCAL_ONLY=true once it is cached.",
                self.model_name,
                _hf_cache_hint(),
            )
            logger.debug("Underlying error", exc_info=True)
        else:
            self._load_error_kind = "model_load_failed"
            logger.exception("Could not load embedding model %s", self.model_name)

    def _warmup(self) -> None:
        """Run one tiny batch so the first real request is not the first CUDA call."""
        try:
            self._encode_texts(["warm up the encoder", "short warmup sentence"], self.batch_size)
            logger.info("Embedding warmup complete on %s", self.device)
        except EmbeddingError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Embedding warmup failed (%s); continuing", type(exc).__name__)

    def load_in_background(self) -> None:
        threading.Thread(target=self.load, name="embedding-model-loader", daemon=True).start()

    # -------------------------------------------------------------- metadata
    @property
    def is_ready(self) -> bool:
        return self._model is not None

    @property
    def dimension(self) -> Optional[int]:
        if self._model is None:
            return None
        # sentence-transformers renamed this method (get_embedding_dimension in newer
        # releases); support both without emitting a deprecation warning.
        getter = getattr(self._model, "get_embedding_dimension", None) or getattr(
            self._model, "get_sentence_embedding_dimension"
        )
        return int(getter())

    def status(self) -> Dict[str, object]:
        runtime = hardware.describe()
        return {
            "model": self.model_name,
            "loaded": self.is_ready,
            "dimension": self.dimension,
            "load_seconds": self._load_seconds,
            "load_attempts": self._load_attempts,
            "error": self._load_error,
            "error_kind": self._load_error_kind,
            "cache_entries": len(self._cache),
            "encode_calls": self._encode_calls,
            "sentences_encoded": self._encode_sentences,
            "framework": (
                f"PyTorch {runtime['torch']['version'] or '(unknown)'} ({self.device})"
            ),
            "normalised": True,
            "local_files_only": Config.MODEL_LOCAL_ONLY,
            # ------------------------------------------------------- hardware
            "device": self.device,
            "device_requested": Config.DEVICE,
            "cuda_available": runtime["cuda"]["available"],
            "gpu_name": runtime["gpu"]["name"],
            "gpu_total_vram_mb": runtime["gpu"]["total_vram_mb"],
            "torch_version": runtime["torch"]["version"],
            "cuda_version": runtime["cuda"]["version"],
            "batch_size": self.batch_size,
            "fallback_reason": self._fallback_reason,
            "oom_events": self._oom_events,
            "oom_retries": self._oom_retries,
        }

    # ------------------------------------------------------------- encoding
    def _cache_get(self, key: str) -> Optional[np.ndarray]:
        with self._cache_lock:
            vector = self._cache.get(key)
            if vector is not None:
                self._cache.move_to_end(key)
            return vector

    def _cache_put(self, key: str, vector: np.ndarray) -> None:
        with self._cache_lock:
            self._cache[key] = vector
            self._cache.move_to_end(key)
            while len(self._cache) > Config.EMBEDDING_CACHE_SIZE:
                self._cache.popitem(last=False)

    def _run_model(self, texts: Sequence[str], batch_size: int) -> np.ndarray:
        """One forward pass over ``texts`` with gradients disabled."""
        import torch

        with torch.inference_mode():          # cheaper and safer than no_grad
            encoded = self._model.encode(
                list(texts),
                batch_size=batch_size,
                normalize_embeddings=True,     # unit length => cosine == dot product
                convert_to_numpy=True,
                show_progress_bar=False,
                device=self.device,
            )
        return np.asarray(encoded, dtype=np.float32)

    def _clear_device_cache(self) -> None:
        if self.device != "cuda":
            return
        try:
            import torch

            torch.cuda.empty_cache()
        except Exception:  # pragma: no cover - defensive
            pass

    def _switch_to_cpu(self, reason: str) -> None:
        """Move the loaded model to CPU for the remainder of the session."""
        import torch

        logger.warning("Switching embedding inference to CPU: %s", reason)
        self._model.to("cpu")
        self._device = "cpu"
        self._batch_size = hardware.resolve_batch_size("cpu")
        self._fallback_reason = reason
        self._clear_device_cache()
        try:
            torch.cuda.synchronize()
        except Exception:  # pragma: no cover - defensive
            pass

    def _handle_oom(self, exc: BaseException, batch_size: int) -> int:
        """React to an out-of-memory error and return the batch size to retry with."""
        self._oom_events += 1
        self._oom_retries += 1
        self._clear_device_cache()

        if batch_size > 1:
            smaller = max(1, batch_size // 2)
            logger.warning(
                "CUDA out of memory at batch_size=%s — retrying with batch_size=%s on %s",
                batch_size,
                smaller,
                self.device,
            )
            self._batch_size = smaller
            return smaller

        if self.device == "cuda" and Config.CUDA_OOM_CPU_FALLBACK:
            self._switch_to_cpu(
                "CUDA ran out of memory even for a single sentence; inference continues on CPU"
            )
            return self.batch_size

        raise EmbeddingError(
            "The embedding model ran out of memory on the GPU. Close other GPU applications, "
            "or set VERITEXT_DEVICE=cpu (or VERITEXT_EMBED_BATCH=8) and run the analysis again. "
            f"Details: {type(exc).__name__}: {str(exc).splitlines()[0][:200]}"
        )

    def _encode_texts(self, texts: Sequence[str], batch_size: int) -> np.ndarray:
        """Encode ``texts`` in batches, shrinking the batch after an OOM."""
        vectors: List[np.ndarray] = []
        index = 0
        current = max(1, batch_size)
        while index < len(texts):
            chunk = list(texts[index:index + current])
            try:
                vectors.append(self._run_model(chunk, current))
            except Exception as exc:
                if not _looks_like_oom(exc):
                    raise
                current = self._handle_oom(exc, current)
                continue            # retry the same sentences with the new batch size
            index += len(chunk)
        if not vectors:
            return np.zeros((0, self.dimension or 384), dtype=np.float32)
        return np.vstack(vectors)

    def encode(
        self,
        sentences: Sequence[str],
        batch_size: Optional[int] = None,
        use_cache: bool = True,
        progress_label: str = "",
    ) -> np.ndarray:
        """
        Encode sentences into an ``(n, 384)`` float32 matrix of unit vectors.

        * identical sentences (within a request or across requests) hit an LRU
          cache, so comparing a document against several sources does not re-encode
          unchanged text;
        * encoding happens in batches to bound memory use on long documents;
        * a CUDA out-of-memory error halves the batch before retrying, then falls
          back to CPU, so a 4 GB GPU degrades instead of crashing the analysis.
        """
        if not sentences:
            return np.zeros((0, self.dimension or 384), dtype=np.float32)
        if not self.load():
            raise EmbeddingError(
                "The sentence-embedding model is not available, so no similarity could be "
                f"computed. {self.load_error_message()}"
            )

        batch_size = max(1, batch_size or self.batch_size)
        keys = [_model_key(s) for s in sentences]

        output: List[Optional[np.ndarray]] = [None] * len(sentences)
        pending_positions: List[int] = []
        if use_cache:
            for position, key in enumerate(keys):
                cached = self._cache_get(key)
                if cached is not None:
                    output[position] = cached
                else:
                    pending_positions.append(position)
        else:
            pending_positions = list(range(len(sentences)))

        if pending_positions:
            pending_texts = [sentences[p] for p in pending_positions]
            started = time.perf_counter()
            stacked = self._encode_texts(pending_texts, batch_size)
            for offset, position in enumerate(pending_positions):
                vector = stacked[offset]
                output[position] = vector
                if use_cache and len(sentences[position]) >= 3:
                    self._cache_put(keys[position], vector)
            elapsed = time.perf_counter() - started
            self._encode_calls += 1
            self._encode_sentences += len(pending_texts)
            logger.debug(
                "Encoded %s sentence(s) on %s in %.2fs%s",
                len(pending_texts),
                self.device,
                elapsed,
                f" ({progress_label})" if progress_label else "",
            )

        matrix = np.vstack([v for v in output if v is not None]).astype(np.float32)
        # Guard against any numerical drift: re-normalise rows.
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms

    def load_error_message(self) -> str:
        if self._load_error_kind == "model_download_failed":
            return (
                "The pretrained model is not in the local Hugging Face cache and could not be "
                "downloaded (no network connection or the hub was unreachable). Connect to the "
                "internet once so the model can be cached, then restart the backend — VeriText "
                "never substitutes placeholder scores when the model is missing."
            )
        return f"Details: {self._load_error or 'unknown error'}"

    def encode_paragraphs(self, sentences: Sequence[str]) -> np.ndarray:
        """
        Paragraph representation = L2-normalised mean of its sentence vectors.

        This keeps the paragraph signal interpretable (it is the average meaning of
        its sentences) and costs no extra transformer passes.
        """
        if len(sentences) == 0:
            return np.zeros((0, self.dimension or 384), dtype=np.float32)
        matrix = self.encode(list(sentences))
        centroid = matrix.mean(axis=0, keepdims=True)
        norm = np.linalg.norm(centroid, axis=1, keepdims=True)
        norm[norm == 0] = 1.0
        return (centroid / norm).astype(np.float32)

    # --------------------------------------------------------------- upkeep
    def clear_cache(self) -> None:
        with self._cache_lock:
            self._cache.clear()


def _hf_cache_hint() -> str:
    import os

    return os.environ.get("HF_HOME") or os.environ.get("TRANSFORMERS_CACHE") or "~/.cache/huggingface"


def get_embedding_service() -> EmbeddingService:
    return EmbeddingService.instance()
