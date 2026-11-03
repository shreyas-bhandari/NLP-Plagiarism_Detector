"""
Document endpoints.

Routes stay thin: validation -> service -> response. No NLP logic here.
Uploaded bytes are written to a private temp file, extracted, and deleted
immediately; only the *derived* structure is cached in the TTL session store.
"""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
import time
import uuid

from flask import Blueprint, request

from config import Config
from services.document_extractor import ExtractionError, extract_document
from services.document_store import get_store
from services.text_preprocessor import prepare_document
from utils.responses import error, ok
from utils.validators import ValidationError, validate_upload

logger = logging.getLogger(__name__)
document_bp = Blueprint("documents", __name__, url_prefix="/api/documents")


def _preview(prepared: dict, max_chars: int = 1200) -> dict:
    paragraphs = [p for p in prepared["paragraphs"] if p["text"].strip()]
    text = "\n\n".join(p["text"] for p in paragraphs[:3])
    return {
        "excerpt": text[:max_chars],
        "paragraph_count": len(paragraphs),
        "first_paragraphs": [
            {"index": p["index"], "page": p.get("page", 0), "text": p["text"][:400]}
            for p in paragraphs[:3]
        ],
    }


def _store_uploaded_document(file_storage, label: str, options: dict) -> dict:
    """Validate -> temp file -> extract -> prepare -> cache. Temp file is always removed."""
    meta = validate_upload(file_storage, f"Document {label}")
    started = time.perf_counter()
    Config.TEMP_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    handle, temp_path = tempfile.mkstemp(
        prefix="veritext_", suffix=f".{meta['extension']}", dir=str(Config.TEMP_UPLOAD_DIR)
    )
    try:
        with os.fdopen(handle, "wb") as temp_file:
            file_storage.stream.seek(0)
            temp_file.write(file_storage.stream.read())
            temp_file.flush()
            os.fsync(temp_file.fileno())

        with open(temp_path, "rb") as reader:
            digest = hashlib.sha256(reader.read()).hexdigest()

        extracted = extract_document(temp_path, original_filename=meta["filename"])
        prepared = prepare_document(extracted, label=label, options=options)
        prepared["metadata"]["sha256"] = digest
        prepared["metadata"]["upload_size_bytes"] = meta["size"]
        prepared["processing_ms"] = int((time.perf_counter() - started) * 1000)
        prepared["label"] = label
        return prepared
    finally:
        # Remove the uploaded file in every case (success, invalid content, crash).
        try:
            os.unlink(temp_path)
        except OSError:  # pragma: no cover
            logger.warning("Temporary upload file could not be removed")


@document_bp.post("/upload")
def upload_document():
    """
    POST /api/documents/upload   (multipart/form-data: file, optional label=A|B)

    Returns document metadata and a short preview. The parsed document is cached
    for ``SESSION_TEXT_TTL_MINUTES`` so the comparison step does not need the file
    to be uploaded twice.
    """
    file_storage = request.files.get("file")
    label = (request.form.get("label") or "A").strip().upper()[:1] or "A"
    options = {
        "exclude_references": request.form.get("exclude_references", "true").lower() != "false",
        "exclude_headings": True,
        "ignore_quotations": request.form.get("ignore_quotations", "false").lower() == "true",
    }

    try:
        prepared = _store_uploaded_document(file_storage, label, options)
    except ValidationError as exc:
        return error("invalid_upload", exc.message, exc.status_code, exc.details)
    except ExtractionError as exc:
        return error(exc.code, exc.message, exc.status_code, hint=exc.hint)

    document_id = f"doc_{uuid.uuid4().hex[:16]}"
    get_store().put(document_id, "document", prepared)

    payload = {
        "document_id": document_id,
        "label": label,
        "filename": prepared["filename"],
        "file_type": prepared["file_type"],
        "word_count": prepared["word_count"],
        "char_count": prepared["char_count"],
        "page_count": prepared["page_count"],
        "paragraph_count": prepared["paragraph_count"],
        "sentence_count": prepared["sentence_count"],
        "eligible_sentence_count": prepared["eligible_sentence_count"],
        "sections_present": prepared["sections_present"],
        "warnings": prepared["warnings"],
        "preview": _preview(prepared),
        "processing_ms": prepared["processing_ms"],
        "retention_minutes": Config.SESSION_TEXT_TTL_MINUTES,
    }
    logger.info(
        "Uploaded document %s (%s, %s words, %s sentences)",
        document_id, prepared["file_type"], prepared["word_count"], prepared["sentence_count"],
    )
    return ok(payload, 201, "Document uploaded and parsed successfully.")


@document_bp.get("/<document_id>")
def get_document(document_id: str):
    """Metadata + preview for a document still held in the session store."""
    prepared = get_store().get(document_id, kind="document")
    if prepared is None:
        return error(
            "document_expired",
            "This document is no longer held in the session cache (it expired or was deleted). "
            "Upload it again to run a comparison.",
            410,
        )
    return ok({
        "document_id": document_id,
        "label": prepared["label"],
        "filename": prepared["filename"],
        "file_type": prepared["file_type"],
        "word_count": prepared["word_count"],
        "sentence_count": prepared["sentence_count"],
        "eligible_sentence_count": prepared["eligible_sentence_count"],
        "paragraph_count": prepared["paragraph_count"],
        "sections_present": prepared["sections_present"],
        "warnings": prepared["warnings"],
        "preview": _preview(prepared),
        "retention_minutes": Config.SESSION_TEXT_TTL_MINUTES,
    })


@document_bp.delete("/<document_id>")
def delete_document(document_id: str):
    """Remove a cached upload before it expires (privacy control)."""
    removed = get_store().delete(document_id)
    if not removed:
        return error("document_not_found", "No cached document with that identifier.", 404)
    return ok({"document_id": document_id, "deleted": True}, 200, "Cached document removed.")
