"""Consistent JSON envelope helpers + uniform error handling."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

from flask import jsonify

logger = logging.getLogger(__name__)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def ok(data: Any = None, status: int = 200, message: Optional[str] = None):
    body: Dict[str, Any] = {"success": True}
    if message:
        body["message"] = message
    if data is not None:
        body["data"] = data
    return jsonify(body), status


def error(
    code: str,
    message: str,
    status: int = 400,
    details: Optional[Dict[str, Any]] = None,
    hint: Optional[str] = None,
):
    body: Dict[str, Any] = {
        "success": False,
        "error": {"code": code, "message": message},
    }
    if details:
        body["error"]["details"] = details
    if hint:
        body["error"]["hint"] = hint
    return jsonify(body), status
