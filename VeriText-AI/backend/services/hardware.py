"""
Hardware and runtime detection.

The NLP engine runs on whatever this module resolves: an NVIDIA GPU through a
CUDA-enabled PyTorch build when one is genuinely available, otherwise the CPU.
Nothing here guesses. If CUDA cannot be used we say why — a missing CUDA build,
no driver, an unsupported device request — and fall back explicitly.

The result is reported verbatim by ``GET /api/health`` and printed by
``python check_environment.py``, so what the interface shows is what the process
is really doing.
"""

from __future__ import annotations

import logging
import platform
import sys
from functools import lru_cache
from typing import Any, Dict, List, Optional

from config import Config

logger = logging.getLogger(__name__)

SUPPORTED_PYTHON = (3, 10)
RECOMMENDED_PYTHON = (3, 11, 3, 12)


def _import_torch():
    """Import torch lazily so the API can explain a missing dependency."""
    try:
        import torch  # noqa: PLC0415 - intentional lazy import

        return torch, None
    except Exception as exc:  # pragma: no cover - depends on the environment
        return None, f"{type(exc).__name__}: {exc}"


def python_report() -> Dict[str, Any]:
    version = platform.python_version()
    supported = sys.version_info[:2] >= SUPPORTED_PYTHON
    return {
        "version": version,
        "implementation": platform.python_implementation(),
        "supported": supported,
        "recommended": "3.11 or 3.12 (3.10+ required)",
    }


def _resolve_device(torch, notes: List[str]) -> str:
    """Decide which device to run on, recording *why* in ``notes``."""
    requested = (Config.DEVICE or "auto").strip().lower()
    if torch is None:
        notes.append("PyTorch is not importable, so the engine falls back to CPU.")
        return "cpu"

    cuda_available = bool(torch.cuda.is_available())
    mps_available = bool(
        getattr(getattr(torch, "backends", None), "mps", None)
        and torch.backends.mps.is_available()
    )

    if requested in {"auto", ""}:
        if cuda_available:
            return "cuda"
        if mps_available:
            notes.append("No CUDA GPU detected; using Apple MPS acceleration.")
            return "mps"
        if torch.version.cuda is None:
            notes.append(
                "This PyTorch build was installed without CUDA (torch.version.cuda is None), "
                "so inference runs on CPU. Install a CUDA-enabled wheel to use the GPU."
            )
        else:
            notes.append(
                "A CUDA-enabled PyTorch build is installed but torch.cuda.is_available() is "
                "False (no driver or no visible GPU); running on CPU."
            )
        return "cpu"

    if requested == "cuda":
        if cuda_available:
            return "cuda"
        notes.append(
            "VERITEXT_DEVICE=cuda was requested but CUDA is unavailable in this environment; "
            "falling back to CPU."
        )
        return "cpu"

    if requested == "mps":
        if mps_available:
            return "mps"
        notes.append("VERITEXT_DEVICE=mps was requested but MPS is unavailable; using CPU.")
        return "cpu"

    if requested == "cpu":
        if cuda_available:
            notes.append("VERITEXT_DEVICE=cpu was requested; the GPU is available but unused.")
        return "cpu"

    notes.append(f"Unknown VERITEXT_DEVICE value {Config.DEVICE!r}; using CPU.")
    return "cpu"


@lru_cache(maxsize=1)
def describe() -> Dict[str, Any]:
    """Return a snapshot of the runtime: Python, PyTorch, CUDA and the GPU.

    Cached because device visibility does not change while the process lives. The
    dict is JSON-serialisable and is embedded directly in ``/api/health``.
    """
    torch, torch_error = _import_torch()
    notes: List[str] = []

    python = python_report()
    if not python["supported"]:
        notes.append(
            f"Python {python['version']} is below the supported minimum "
            f"({SUPPORTED_PYTHON[0]}.{SUPPORTED_PYTHON[1]}+)."
        )

    resolved = _resolve_device(torch, notes)

    torch_info: Dict[str, Any] = {
        "available": torch is not None,
        "version": getattr(torch, "__version__", None),
        "cuda_build": getattr(getattr(torch, "version", None), "cuda", None),
        "cudnn_version": None,
        "threads": Config.TORCH_THREADS,
        "error": torch_error,
    }
    if torch is not None:
        try:
            if torch.backends.cudnn.is_available():
                torch_info["cudnn_version"] = torch.backends.cudnn.version()
        except Exception:  # pragma: no cover - platform dependent
            pass

    cuda: Dict[str, Any] = {
        "available": False,
        "device_count": 0,
        "version": getattr(getattr(torch, "version", None), "cuda", None) if torch else None,
    }
    gpu: Dict[str, Any] = {
        "name": None,
        "index": None,
        "total_vram_mb": None,
        "free_vram_mb": None,
        "compute_capability": None,
    }

    if torch is not None:
        try:
            cuda["available"] = bool(torch.cuda.is_available())
            cuda["device_count"] = int(torch.cuda.device_count()) if cuda["available"] else 0
        except Exception as exc:  # pragma: no cover - broken driver
            notes.append(f"CUDA query failed: {type(exc).__name__}: {exc}")

        if cuda["available"]:
            try:
                index = torch.cuda.current_device()
                props = torch.cuda.get_device_properties(index)
                free_bytes, total_bytes = torch.cuda.mem_get_info(index)
                gpu.update(
                    {
                        "name": props.name,
                        "index": int(index),
                        "total_vram_mb": round(total_bytes / (1024 ** 2)),
                        "free_vram_mb": round(free_bytes / (1024 ** 2)),
                        "compute_capability": f"{props.major}.{props.minor}",
                    }
                )
                if resolved != "cuda":
                    notes.append(f"GPU {props.name} is present but not used for inference.")
            except Exception as exc:  # pragma: no cover - driver level failure
                notes.append(f"Could not read GPU properties: {type(exc).__name__}: {exc}")

    return {
        "python": python,
        "torch": torch_info,
        "cuda": cuda,
        "device": {
            "requested": Config.DEVICE,
            "resolved": resolved,
            "type": resolved,
            "name": gpu["name"] if resolved == "cuda" else platform.processor() or "CPU",
            "inference_on_gpu": resolved in {"cuda", "mps"},
        },
        "gpu": gpu,
        "batch": {
            "effective": resolve_batch_size(resolved),
            "gpu_default": Config.EMBEDDING_BATCH_GPU,
            "cpu_default": Config.EMBEDDING_BATCH_CPU,
            "override": Config.EMBEDDING_BATCH_SIZE or None,
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        },
        "notes": notes,
    }


def resolve_batch_size(device: Optional[str] = None) -> int:
    """Effective embedding batch size for a device.

    Order of precedence: explicit ``VERITEXT_EMBED_BATCH`` override, then the
    per-device default (16 on GPU so a 4 GB RTX 3050 has headroom, 32 on CPU).
    """
    if Config.EMBEDDING_BATCH_SIZE and Config.EMBEDDING_BATCH_SIZE > 0:
        return max(1, Config.EMBEDDING_BATCH_SIZE)
    target = device or describe()["device"]["resolved"]
    if target == "cuda":
        return max(1, Config.EMBEDDING_BATCH_GPU)
    return max(1, Config.EMBEDDING_BATCH_CPU)


def resolved_device() -> str:
    return describe()["device"]["resolved"]


def summary_line() -> str:
    """One-line human summary used in startup logs."""
    info = describe()
    device = info["device"]["resolved"]
    if device == "cuda":
        return f"device=cuda ({info['gpu']['name']}, {info['gpu']['total_vram_mb']} MB VRAM)"
    return f"device={device} (CPU fallback)"


def log_startup_report() -> None:
    info = describe()
    logger.info(
        "Runtime: Python %s · PyTorch %s (CUDA build %s) · device=%s%s · batch=%s",
        info["python"]["version"],
        info["torch"]["version"] or "not installed",
        info["torch"]["cuda_build"] or "none",
        info["device"]["resolved"],
        f" ({info['gpu']['name']})" if info["device"]["resolved"] == "cuda" else "",
        info["batch"]["effective"],
    )
    for note in info["notes"]:
        logger.info("Runtime note: %s", note)
