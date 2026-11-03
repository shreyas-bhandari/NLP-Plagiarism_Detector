"""
Analysis endpoints: run a comparison, read results, download the PDF report.

Two input styles are supported so the API is usable both from the web UI and
from scripts:

* ``application/json``  -> ``{"doc_a_id": "doc_...", "doc_b_id": "doc_...", "options": {...}}``
  (documents previously posted to /api/documents/upload)
* ``multipart/form-data`` -> ``file_a``, ``file_b`` and an optional JSON ``options`` field
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from io import BytesIO

from flask import Blueprint, request, send_file

from config import Config
from models import database
from routes.document_routes import _store_uploaded_document
from services.document_extractor import ExtractionError
from services.document_store import get_store
from services.embedding_service import EmbeddingError
from services.plagiarism_detector import detect_plagiarism
from services.report_generator import generate_pdf_report
from utils.responses import error, new_id, ok
from utils.validators import ValidationError, validate_compare_payload

logger = logging.getLogger(__name__)
analysis_bp = Blueprint("analysis", __name__, url_prefix="/api/analysis")


def _resolve_documents():
    """Load both documents from the session cache (JSON) or from the request (multipart)."""
    if request.files:
        raw_options = request.form.get("options")
        try:
            options = json.loads(raw_options) if raw_options else {}
        except json.JSONDecodeError:
            raise ValidationError("'options' must be valid JSON when sent as a form field.", 400)
        options = validate_compare_payload({"options": options})

        prep_a = _store_uploaded_document(request.files.get("file_a"), "A", options)
        prep_b = _store_uploaded_document(request.files.get("file_b"), "B", options)
        return prep_a, prep_b, options

    payload = request.get_json(silent=True) or {}
    options = validate_compare_payload(payload)
    doc_a_id = (payload.get("doc_a_id") or "").strip()
    doc_b_id = (payload.get("doc_b_id") or "").strip()
    if not doc_a_id or not doc_b_id:
        raise ValidationError(
            "Provide 'doc_a_id' and 'doc_b_id' (from /api/documents/upload), or upload "
            "'file_a' and 'file_b' as multipart form data.",
            400,
        )
    if doc_a_id == doc_b_id:
        raise ValidationError("Document A and Document B must be different uploads.", 400)

    store = get_store()
    prep_a = store.get(doc_a_id, kind="document")
    prep_b = store.get(doc_b_id, kind="document")
    missing = [label for label, prep in (("A", prep_a), ("B", prep_b)) if prep is None]
    if missing:
        raise ValidationError(
            f"Document {' and '.join(missing)} is no longer available in the session cache "
            f"(uploads expire after {Config.SESSION_TEXT_TTL_MINUTES} minutes). Upload it again.",
            410,
        )
    # Re-apply segmentation options chosen for this comparison.
    prep_a["label"], prep_b["label"] = "A", "B"
    return prep_a, prep_b, options


@analysis_bp.post("/compare")
def compare_documents():
    """
    POST /api/analysis/compare — run the semantic + lexical comparison.

    Synchronous by design: one comparison of two realistic academic documents
    takes a fraction of a second to a few seconds depending on the detected device
    (GPU or CPU), which keeps the API simple and debuggable.
    """
    started = time.perf_counter()
    analysis_id = new_id("an")
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    try:
        prep_a, prep_b, options = _resolve_documents()
    except ValidationError as exc:
        return error("invalid_request", exc.message, exc.status_code, exc.details)
    except ExtractionError as exc:
        return error(exc.code, exc.message, exc.status_code, hint=exc.hint)

    try:
        result = detect_plagiarism(prep_a, prep_b, options)
    except EmbeddingError as exc:
        # The model is missing or failed (for example the first-run download could not
        # reach Hugging Face, or the GPU ran out of memory with CPU fallback disabled).
        # Return the actionable reason: VeriText never reports placeholder scores.
        logger.error("Analysis %s could not run: %s", analysis_id, exc)
        database.mark_analysis_failed(
            analysis_id, prep_a.get("filename", "document A"), prep_b.get("filename", "document B"),
            f"EmbeddingError: {exc}", options,
        )
        return error(
            "embedding_unavailable",
            str(exc),
            503,
            hint=(
                "Run `python check_environment.py` in the backend folder, or check "
                "GET /api/health for the detected device and model status."
            ),
        )
    except Exception as exc:  # NLP failure: log the detail, return a safe message
        logger.exception("Analysis %s failed", analysis_id)
        database.mark_analysis_failed(
            analysis_id, prep_a.get("filename", "document A"), prep_b.get("filename", "document B"),
            f"{type(exc).__name__}: {exc}", options,
        )
        return error(
            "analysis_failed",
            "The analysis could not be completed. Please try again; if the problem persists, "
            "check the server log.",
            500,
        )

    result["analysis_id"] = analysis_id
    result["created_at"] = created_at
    result["status"] = "completed"

    try:
        database.save_analysis({"id": analysis_id, "created_at": created_at}, result)
        database.save_document_metadata(
            f"{analysis_id}-A", prep_a["filename"], prep_a["file_type"],
            prep_a["word_count"], prep_a["char_count"], prep_a["page_count"],
            prep_a["metadata"].get("sha256", ""),
        )
        database.save_document_metadata(
            f"{analysis_id}-B", prep_b["filename"], prep_b["file_type"],
            prep_b["word_count"], prep_b["char_count"], prep_b["page_count"],
            prep_b["metadata"].get("sha256", ""),
        )
    except Exception:
        logger.exception("Could not persist analysis %s", analysis_id)

    # Cache the parsed documents so the comparison viewer can render highlighted
    # text without keeping anything permanently.
    get_store().put(analysis_id, "analysis", {"A": prep_a, "B": prep_b})
    result["session_text_available"] = get_store().get(analysis_id, kind="analysis") is not None
    result["retention_minutes"] = Config.SESSION_TEXT_TTL_MINUTES
    result["request_ms"] = int((time.perf_counter() - started) * 1000)

    logger.info(
        "Analysis %s complete in %sms (weighted index %.3f, %s primary matches)",
        analysis_id, result["request_ms"], result["summary"]["weighted_similarity"],
        result["summary"]["primary_matches"],
    )
    return ok(result, 201, "Analysis completed.")


@analysis_bp.get("/<analysis_id>")
def get_analysis(analysis_id: str):
    record = database.get_analysis(analysis_id)
    if record is None:
        return error("analysis_not_found", "No analysis with that identifier.", 404)
    if record["status"] == "failed":
        return ok({
            "analysis_id": analysis_id,
            "status": "failed",
            "error_message": record.get("error_message"),
            "created_at": record.get("created_at"),
        })
    result = record.pop("result", None) or {}
    result["analysis_id"] = analysis_id
    result["status"] = "completed"
    result["created_at"] = record.get("created_at")
    result["session_text_available"] = get_store().get(analysis_id, kind="analysis") is not None
    result["retention_minutes"] = Config.SESSION_TEXT_TTL_MINUTES
    return ok(result)


@analysis_bp.get("/<analysis_id>/documents")
def get_analysis_documents(analysis_id: str):
    """Full segmented text of both documents, for the side-by-side viewer."""
    payload = get_store().get(analysis_id, kind="analysis")
    if payload is None:
        return error(
            "document_text_expired",
            "The document text for this analysis is no longer retained. VeriText AI deletes "
            f"extracted text after {Config.SESSION_TEXT_TTL_MINUTES} minutes for privacy. "
            "The scored results, matches and report remain available.",
            410,
        )
    return ok({
        "analysis_id": analysis_id,
        "A": payload["A"],
        "B": payload["B"],
        "retention_minutes": Config.SESSION_TEXT_TTL_MINUTES,
    })


@analysis_bp.get("/<analysis_id>/report")
def download_report(analysis_id: str):
    """Generate the PDF report on demand and stream it (never stored publicly)."""
    record = database.get_analysis(analysis_id)
    if record is None:
        return error("analysis_not_found", "No analysis with that identifier.", 404)
    if record["status"] != "completed" or not record.get("result"):
        return error("report_unavailable", "A report can only be generated for a completed analysis.", 409)

    try:
        pdf_bytes = generate_pdf_report(analysis_id, record["result"], record.get("created_at"))
    except Exception:
        logger.exception("Report generation failed for %s", analysis_id)
        return error("report_failed", "The PDF report could not be generated.", 500)

    filename = f"VeriText-report-{analysis_id}.pdf"
    response = send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
        max_age=0,
    )
    response.headers["Cache-Control"] = "no-store, private"
    return response


@analysis_bp.get("/<analysis_id>/export")
def export_analysis(analysis_id: str):
    """Raw JSON export — useful for research notebooks and reproducible audits."""
    record = database.get_analysis(analysis_id)
    if record is None:
        return error("analysis_not_found", "No analysis with that identifier.", 404)
    if not record.get("result"):
        return error("export_unavailable", "Nothing to export for this analysis.", 409)
    buffer = BytesIO(json.dumps(record["result"], indent=2).encode("utf-8"))
    response = send_file(
        buffer, mimetype="application/json", as_attachment=True,
        download_name=f"VeriText-analysis-{analysis_id}.json", max_age=0,
    )
    response.headers["Cache-Control"] = "no-store, private"
    return response


@analysis_bp.delete("/<analysis_id>")
def delete_analysis(analysis_id: str):
    """Delete an analysis, its match rows and any retained document text."""
    deleted = database.delete_analysis(analysis_id)
    store = get_store()
    store.delete(analysis_id)
    store.delete_prefix(f"{analysis_id}-")
    if not deleted:
        return error("analysis_not_found", "No analysis with that identifier.", 404)
    return ok({"analysis_id": analysis_id, "deleted": True}, 200, "Analysis deleted.")
