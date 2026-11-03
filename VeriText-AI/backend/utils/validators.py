"""
Request validation helpers.

Everything an API client can send is validated here so that route handlers stay
thin and NLP services never receive malformed input.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from config import Config


class ValidationError(Exception):
    def __init__(self, message: str, status_code: int = 400, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


_MAGIC_SIGNATURES = {
    "pdf": (b"%PDF",),
    "docx": (b"PK\x03\x04",),
}


def safe_filename(name: str) -> str:
    """
    Produce a filesystem-safe name. Keeps the human-readable stem for display but
    strips directories, control characters and exotic extensions.
    """
    cleaned = secure_filename(name or "document")
    if not cleaned:
        cleaned = "document"
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", cleaned)
    return cleaned[:120]


def file_extension(name: str) -> str:
    return Path(name or "").suffix.lower().lstrip(".")


def validate_upload(file: Optional[FileStorage], label: str) -> Dict[str, Any]:
    """
    Validate an uploaded file without reading it into memory as a whole.

    Checks: presence, non-empty, allowed extension, size limit and (for the
    binary formats we support) that the file signature matches the extension.
    """
    if file is None:
        raise ValidationError(f"{label}: no file was provided.", 400)
    if not getattr(file, "filename", ""):
        raise ValidationError(f"{label}: the uploaded file has no filename.", 400)

    filename = safe_filename(file.filename)
    extension = file_extension(filename)
    if extension not in Config.ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"{label}: '.{extension or 'unknown'}' files are not supported. "
            f"Allowed: {', '.join(sorted(Config.ALLOWED_EXTENSIONS))}.",
            415,
        )

    # Determine size without trusting the client-provided content length.
    stream = file.stream
    position = stream.tell() if hasattr(stream, "tell") else 0
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(position)
    if size == 0:
        raise ValidationError(f"{label}: the uploaded file is empty.", 400)
    if size > Config.MAX_CONTENT_LENGTH:
        raise ValidationError(
            f"{label}: file is {size / 1024 / 1024:.1f} MB, above the "
            f"{Config.MAX_UPLOAD_MB} MB limit.",
            413,
        )

    signatures = _MAGIC_SIGNATURES.get(extension)
    if signatures:
        head = stream.read(8)
        stream.seek(0)
        if not any(head.startswith(sig) for sig in signatures):
            raise ValidationError(
                f"{label}: the file content does not look like a valid "
                f"{extension.upper()} file.",
                415,
            )

    return {"filename": filename, "extension": extension, "size": size}


def validate_compare_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Normalise and validate the analysis options accepted by /api/analysis/compare.

    Unknown keys are ignored; every value is clamped to a sane range so that a
    malicious or buggy client cannot force an unbounded computation.
    """
    payload = payload or {}
    options = payload.get("options") or {}
    if not isinstance(options, dict):
        raise ValidationError("'options' must be an object.", 400)

    def as_bool(key: str, default: bool) -> bool:
        value = options.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in {"1", "true", "yes", "on"}
        return default

    def as_float(key: str, default: float, low: float, high: float) -> float:
        value = options.get(key, default)
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValidationError(f"options.{key} must be a number.", 400)
        if not (low <= number <= high):
            raise ValidationError(
                f"options.{key} must be between {low} and {high}.", 400
            )
        return number

    def as_int(key: str, default: int, low: int, high: int) -> int:
        value = options.get(key, default)
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise ValidationError(f"options.{key} must be an integer.", 400)
        if not (low <= number <= high):
            raise ValidationError(f"options.{key} must be between {low} and {high}.", 400)
        return number

    cleaned = {
        "exclude_references": as_bool("exclude_references", True),
        "exclude_headings": as_bool("exclude_headings", True),
        "ignore_quotations": as_bool("ignore_quotations", False),
        "semantic_threshold": as_float(
            "semantic_threshold", Config.SEMANTIC_THRESHOLD, 0.30, 0.99
        ),
        "paragraph_threshold": as_float(
            "paragraph_threshold", Config.PARAGRAPH_THRESHOLD, 0.30, 0.99
        ),
        "top_k": as_int("top_k", Config.TOP_K_PER_SENTENCE, 1, 5),
        "min_sentence_words": as_int(
            "min_sentence_words", Config.MIN_SENTENCE_WORDS, 3, 40
        ),
    }
    return cleaned
