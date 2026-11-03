"""History + dashboard statistics endpoints (all values come from SQLite)."""

from __future__ import annotations

import logging

from flask import Blueprint, request

from models import database
from services.embedding_service import get_embedding_service
from utils.responses import error, ok

logger = logging.getLogger(__name__)
history_bp = Blueprint("history", __name__, url_prefix="/api")


@history_bp.get("/analysis/history")
def analysis_history():
    """
    GET /api/analysis/history?limit=20&offset=0&search=term

    Returns paginated analysis records (metadata + summary only — no document text).
    """
    try:
        limit = min(max(int(request.args.get("limit", 20)), 1), 100)
        offset = max(int(request.args.get("offset", 0)), 0)
    except ValueError:
        return error("invalid_request", "'limit' and 'offset' must be integers.", 400)
    search = (request.args.get("search") or "").strip()[:120]

    data = database.list_history(limit=limit, offset=offset, search=search)
    return ok(data)


@history_bp.get("/stats/dashboard")
def dashboard_stats():
    """Aggregates for the dashboard (never fabricated: empty database -> zeros)."""
    stats = database.dashboard_stats()
    stats["engine"] = {
        "model": get_embedding_service().model_name,
        "ready": get_embedding_service().is_ready,
    }
    return ok(stats)
