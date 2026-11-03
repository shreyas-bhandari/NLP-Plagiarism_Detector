"""
SQLite persistence layer.

What is stored
--------------
* analysis metadata + the computed result document (JSON) so history and reports
  keep working after the session text cache expires;
* match rows with *snippets only* (truncated, per ``SNIPPET_MAX_CHARS``) for
  querying and analytics;
* document metadata (name, type, sizes, sha256) — never the document itself.

What is **not** stored
----------------------
The full extracted text of uploaded documents. That lives only in the TTL-based
session store (``services/document_store.py``) so the comparison viewer can show
highlighted text, and it is purged on delete or after the TTL.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import Config

logger = logging.getLogger(__name__)
_write_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
    id                  TEXT PRIMARY KEY,
    created_at          TEXT NOT NULL,
    completed_at        TEXT,
    status              TEXT NOT NULL DEFAULT 'completed',
    doc_a_name          TEXT NOT NULL,
    doc_b_name          TEXT NOT NULL,
    doc_a_type          TEXT,
    doc_b_type          TEXT,
    doc_a_words         INTEGER DEFAULT 0,
    doc_b_words         INTEGER DEFAULT 0,
    doc_a_sentences     INTEGER DEFAULT 0,
    doc_b_sentences     INTEGER DEFAULT 0,
    weighted_similarity REAL DEFAULT 0,
    average_matched     REAL DEFAULT 0,
    max_similarity      REAL DEFAULT 0,
    exact_count         INTEGER DEFAULT 0,
    near_exact_count    INTEGER DEFAULT 0,
    semantic_count      INTEGER DEFAULT 0,
    primary_matches     INTEGER DEFAULT 0,
    coverage_a          REAL DEFAULT 0,
    coverage_b          REAL DEFAULT 0,
    duration_ms         INTEGER DEFAULT 0,
    model               TEXT,
    engine_version      TEXT,
    options_json        TEXT,
    warnings_json       TEXT,
    result_json         TEXT,
    error_message       TEXT
);

CREATE TABLE IF NOT EXISTS matches (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id    TEXT NOT NULL,
    match_id       TEXT NOT NULL,
    is_primary     INTEGER DEFAULT 1,
    classification TEXT,
    subtype        TEXT,
    similarity     REAL,
    source_index   INTEGER,
    target_index   INTEGER,
    source_page    INTEGER,
    target_page    INTEGER,
    source_snippet TEXT,
    target_snippet TEXT,
    suppressed     INTEGER DEFAULT 0,
    explanation    TEXT,
    FOREIGN KEY (analysis_id) REFERENCES analyses (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS documents (
    id         TEXT PRIMARY KEY,
    filename   TEXT NOT NULL,
    file_type  TEXT,
    word_count INTEGER DEFAULT 0,
    char_count INTEGER DEFAULT 0,
    page_count INTEGER DEFAULT 0,
    sha256     TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_matches_analysis ON matches (analysis_id);
CREATE INDEX IF NOT EXISTS idx_analyses_created ON analyses (created_at DESC);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def get_connection():
    Config.ensure_directories()
    connection = sqlite3.connect(str(Config.DATABASE_PATH), timeout=20)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    with get_connection() as connection:
        connection.executescript(SCHEMA)
    logger.info("SQLite schema ready at %s", Config.DATABASE_PATH.name)


# --------------------------------------------------------------------------- #
# writes
# --------------------------------------------------------------------------- #
def save_document_metadata(
    document_id: str,
    filename: str,
    file_type: str,
    word_count: int,
    char_count: int,
    page_count: int,
    sha256: str = "",
) -> None:
    with _write_lock, get_connection() as connection:
        connection.execute(
            """INSERT OR REPLACE INTO documents
               (id, filename, file_type, word_count, char_count, page_count, sha256, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (document_id, filename, file_type, word_count, char_count, page_count, sha256, _now()),
        )


def save_analysis(analysis: Dict[str, Any], result: Dict[str, Any]) -> None:
    """Persist an analysis and its match rows in one transaction."""
    summary = result["summary"]
    coverage = summary["coverage"]
    docs = result["documents"]

    with _write_lock, get_connection() as connection:
        connection.execute(
            """INSERT OR REPLACE INTO analyses (
                   id, created_at, completed_at, status, doc_a_name, doc_b_name,
                   doc_a_type, doc_b_type, doc_a_words, doc_b_words, doc_a_sentences,
                   doc_b_sentences, weighted_similarity, average_matched, max_similarity,
                   exact_count, near_exact_count, semantic_count, primary_matches,
                   coverage_a, coverage_b, duration_ms, model, engine_version,
                   options_json, warnings_json, result_json, error_message)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                analysis["id"], analysis["created_at"], _now(), "completed",
                docs["A"]["filename"], docs["B"]["filename"],
                docs["A"]["file_type"], docs["B"]["file_type"],
                docs["A"]["word_count"], docs["B"]["word_count"],
                docs["A"]["sentence_count"], docs["B"]["sentence_count"],
                summary["weighted_similarity"], summary["average_matched_similarity"],
                summary["max_similarity"], summary["exact_matches"], summary["near_exact_matches"],
                summary["semantic_matches"], summary["primary_matches"],
                coverage["A"]["sentence_coverage_pct"], coverage["B"]["sentence_coverage_pct"],
                result["engine"]["timings"]["total_ms"], result["engine"]["model"],
                result["engine"]["version"], json.dumps(result["engine"]["options"]),
                json.dumps(result["warnings"]), json.dumps(result), None,
            ),
        )

        connection.execute("DELETE FROM matches WHERE analysis_id = ?", (analysis["id"],))
        rows = []
        for match in result["matches"]:
            keep_text = Config.RETAIN_SNIPPETS
            rows.append((
                analysis["id"], match["id"], int(match["is_primary"]),
                match["classification"], match["subtype"], match["similarity"],
                match["source"]["index"], match["target"]["index"],
                match["source"]["page"], match["target"]["page"],
                match["source"]["text"][: Config.SNIPPET_MAX_CHARS] if keep_text else "",
                match["target"]["text"][: Config.SNIPPET_MAX_CHARS] if keep_text else "",
                int(match["suppressed"]), json.dumps(match["explanation"]),
            ))
        connection.executemany(
            """INSERT INTO matches (analysis_id, match_id, is_primary, classification,
                   subtype, similarity, source_index, target_index, source_page, target_page,
                   source_snippet, target_snippet, suppressed, explanation)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            rows,
        )


def mark_analysis_failed(analysis_id: str, doc_a: str, doc_b: str, message: str, options: Dict[str, Any]) -> None:
    with _write_lock, get_connection() as connection:
        connection.execute(
            """INSERT OR REPLACE INTO analyses
               (id, created_at, completed_at, status, doc_a_name, doc_b_name,
                options_json, error_message)
               VALUES (?,?,?,?,?,?,?,?)""",
            (analysis_id, _now(), _now(), "failed", doc_a, doc_b, json.dumps(options), message[:500]),
        )


# --------------------------------------------------------------------------- #
# reads
# --------------------------------------------------------------------------- #
def get_analysis(analysis_id: str, include_result: bool = True) -> Optional[Dict[str, Any]]:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM analyses WHERE id = ?", (analysis_id,)
        ).fetchone()
    if row is None:
        return None
    record = dict(row)
    if include_result and record.get("result_json"):
        try:
            record["result"] = json.loads(record["result_json"])
        except json.JSONDecodeError:
            record["result"] = None
    record.pop("result_json", None)
    return record


def list_history(limit: int = 20, offset: int = 0, search: str = "") -> Dict[str, Any]:
    where = ""
    params: List[Any] = []
    if search:
        where = "WHERE doc_a_name LIKE ? OR doc_b_name LIKE ? OR id LIKE ?"
        like = f"%{search}%"
        params = [like, like, like]

    with get_connection() as connection:
        total = connection.execute(
            f"SELECT COUNT(*) FROM analyses {where}", params
        ).fetchone()[0]
        rows = connection.execute(
            f"""SELECT id, created_at, status, doc_a_name, doc_b_name, doc_a_type, doc_b_type,
                       doc_a_words, doc_b_words, weighted_similarity, average_matched,
                       max_similarity, exact_count, near_exact_count, semantic_count,
                       primary_matches, coverage_a, coverage_b, duration_ms, error_message
                FROM analyses {where}
                ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            params + [limit, offset],
        ).fetchall()

    items = []
    for row in rows:
        record = dict(row)
        record["summary"] = {
            "weighted_similarity_pct": round((record.get("weighted_similarity") or 0) * 100, 1),
            "average_matched_similarity_pct": round((record.get("average_matched") or 0) * 100, 1),
            "max_similarity_pct": round((record.get("max_similarity") or 0) * 100, 1),
            "exact_matches": record.get("exact_count") or 0,
            "near_exact_matches": record.get("near_exact_count") or 0,
            "semantic_matches": record.get("semantic_count") or 0,
            "primary_matches": record.get("primary_matches") or 0,
            "coverage_a_pct": record.get("coverage_a") or 0,
            "coverage_b_pct": record.get("coverage_b") or 0,
        }
        items.append(record)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def delete_analysis(analysis_id: str) -> bool:
    with _write_lock, get_connection() as connection:
        cursor = connection.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
        connection.execute("DELETE FROM matches WHERE analysis_id = ?", (analysis_id,))
        return cursor.rowcount > 0


def dashboard_stats() -> Dict[str, Any]:
    """Aggregate metrics computed from real rows (never fabricated)."""
    with get_connection() as connection:
        totals = connection.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                      SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                      AVG(CASE WHEN status = 'completed' THEN duration_ms END) AS avg_ms,
                      AVG(CASE WHEN status = 'completed' THEN weighted_similarity END) AS avg_similarity,
                      SUM(exact_count) AS exact,
                      SUM(near_exact_count) AS near_exact,
                      SUM(semantic_count) AS semantic
               FROM analyses"""
        ).fetchone()
        documents = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        recent = connection.execute(
            """SELECT id, created_at, status, doc_a_name, doc_b_name, weighted_similarity,
                      primary_matches, duration_ms, doc_a_words, doc_b_words
               FROM analyses ORDER BY created_at DESC LIMIT 6"""
        ).fetchall()
        activity = connection.execute(
            """SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS analyses,
                      AVG(weighted_similarity) AS avg_similarity
               FROM analyses
               WHERE created_at >= date('now', '-13 days')
               GROUP BY day ORDER BY day"""
        ).fetchall()

    return {
        "total_analyses": totals["total"] or 0,
        "completed_analyses": totals["completed"] or 0,
        "failed_analyses": totals["failed"] or 0,
        "documents_processed": documents,
        "average_duration_ms": int(totals["avg_ms"] or 0),
        "average_weighted_similarity_pct": round((totals["avg_similarity"] or 0) * 100, 1),
        "total_exact_matches": totals["exact"] or 0,
        "total_near_exact_matches": totals["near_exact"] or 0,
        "total_semantic_matches": totals["semantic"] or 0,
        "recent": [dict(row) for row in recent],
        "activity": [dict(row) for row in activity],
    }
