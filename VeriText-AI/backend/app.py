"""
VeriText AI — Flask application factory.

Run locally:
    cd backend && python app.py
or (production-ish):
    gunicorn -w 1 -b 0.0.0.0:5000 "app:create_app()"

The NLP engine auto-detects its device (CUDA when a CUDA-enabled PyTorch build can
see a GPU, CPU otherwise) — see services/hardware.py. With GPU inference, one
worker process is recommended so the model is loaded into VRAM once and reused for
every request; extra workers would each hold a copy of the model.
"""

from __future__ import annotations

import logging
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from config import Config
from models import database
from routes.analysis_routes import analysis_bp
from routes.document_routes import document_bp
from routes.history_routes import history_bp
from services.document_store import get_store
from services.document_extractor import ExtractionError
from services import hardware
from services.embedding_service import get_embedding_service
from utils.responses import error
from utils.validators import ValidationError

logger = logging.getLogger("veritext")
FRONTEND_DIST = Config.PROJECT_ROOT / "frontend" / "dist"


def configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
        stream=sys.stdout,
    )
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.INFO)


def create_app(load_model: bool = True) -> Flask:
    configure_logging()
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = Config.MAX_CONTENT_LENGTH
    app.config["JSON_SORT_KEYS"] = False
    app.config["PROPAGATE_EXCEPTIONS"] = False

    CORS(app, resources={r"/api/*": {"origins": Config.CORS_ORIGINS}}, supports_credentials=False)

    database.init_db()
    get_store()  # start the TTL sweeper

    app.register_blueprint(document_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(history_bp)

    embedder = get_embedding_service()
    if load_model:
        # Load once at startup so the first real request is not 10s slower.
        embedder.load()
    else:  # pragma: no cover - used by tests
        embedder.load_in_background()

    # ------------------------------------------------------------- lifecycle
    @app.before_request
    def _start_timer():
        request._started_at = time.perf_counter()
        request.request_id = uuid.uuid4().hex[:12]

    @app.after_request
    def _log_and_harden(response):
        duration = int((time.perf_counter() - getattr(request, "_started_at", time.perf_counter())) * 1000)
        if request.path.startswith("/api/"):
            logger.info(
                "%s %s -> %s (%sms) [%s]",
                request.method, request.path, response.status_code, duration,
                getattr(request, "request_id", "-"),
            )
        # Sensible security headers; no inline scripts are used by the SPA build.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if request.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    # --------------------------------------------------------------- errors
    @app.errorhandler(ValidationError)
    def _validation_error(exc: ValidationError):
        return error("invalid_request", exc.message, exc.status_code, exc.details)

    @app.errorhandler(ExtractionError)
    def _extraction_error(exc: ExtractionError):
        return error(exc.code, exc.message, exc.status_code, hint=exc.hint)

    @app.errorhandler(RequestEntityTooLarge)
    def _too_large(exc):
        return error(
            "file_too_large",
            f"The upload exceeds the {Config.MAX_UPLOAD_MB} MB limit.",
            413,
        )

    @app.errorhandler(HTTPException)
    def _http_error(exc: HTTPException):
        return error(exc.name.lower().replace(" ", "_"), exc.description or exc.name, exc.code or 500)

    @app.errorhandler(Exception)
    def _unhandled(exc: Exception):
        logger.error("Unhandled error on %s: %s", request.path, exc)
        logger.debug(traceback.format_exc())
        return error(
            "internal_error",
            "Something went wrong while processing the request. No document content is "
            "included in this message.",
            500,
        )

    # ----------------------------------------------------------------- health
    @app.get("/api/health")
    def health():
        """Service, model and hardware status — every value is read from the process."""
        embedder_status = embedder.status()
        runtime = hardware.describe()
        if embedder_status["loaded"]:
            status = "ok"
        elif embedder_status.get("error_kind") == "model_download_failed":
            status = "model_unavailable"
        else:
            status = "loading"
        return jsonify({
            "success": True,
            "data": {
                "status": status,
                "service": "VeriText AI backend",
                "version": Config.ENGINE_VERSION,
                "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "model": embedder_status,
                # Python, PyTorch, CUDA build, GPU name/VRAM, resolved device, batch size.
                # Reported as detected — nothing here is assumed or fabricated.
                "runtime": runtime,
                "storage": get_store().stats(),
                "limits": {
                    "max_upload_mb": Config.MAX_UPLOAD_MB,
                    "max_document_chars": Config.MAX_DOCUMENT_CHARS,
                    "max_sentences_per_document": Config.MAX_SENTENCES_PER_DOC,
                    "allowed_extensions": sorted(Config.ALLOWED_EXTENSIONS),
                },
                "thresholds": {
                    "semantic_min": Config.SEMANTIC_THRESHOLD,
                    "high": Config.HIGH_SIMILARITY,
                    "moderate": Config.MODERATE_SIMILARITY,
                },
            },
        })

    # ------------------------------------------------- static SPA (production)
    @app.get("/")
    @app.get("/<path:path>")
    def serve_frontend(path: str = ""):
        if path.startswith("api/"):
            return error("not_found", "No such API endpoint.", 404)
        if not FRONTEND_DIST.exists():
            return jsonify({
                "success": True,
                "data": {
                    "message": "VeriText AI backend is running. Frontend build not found.",
                    "hint": "Run `npm install && npm run build` in ./frontend, or use the Vite "
                            "dev server (npm run dev) which proxies /api to this backend.",
                    "api": "/api/health",
                },
            })
        candidate = FRONTEND_DIST / path
        if path and candidate.is_file():
            return send_from_directory(FRONTEND_DIST, path)
        # SPA fallback: let React Router handle client-side routes.
        return send_from_directory(FRONTEND_DIST, "index.html")

    if embedder.is_ready:
        logger.info(
            "VeriText AI backend ready (model=%s on %s, db=%s)",
            Config.MODEL_NAME, embedder.device, Config.DATABASE_PATH.name,
        )
    else:
        logger.error(
            "VeriText AI backend started WITHOUT a working embedding model (%s). Analyses will "
            "return an explicit error until the model can be loaded — see GET /api/health and "
            "`python check_environment.py`.",
            embedder.status().get("error_kind") or "unknown",
        )
    return app


if __name__ == "__main__":
    application = create_app()
    application.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG,
        threaded=True,
        use_reloader=False,
    )
