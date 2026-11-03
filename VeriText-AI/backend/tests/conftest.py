"""Shared pytest fixtures. Tests use a temporary database so real data is untouched."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

SAMPLES = BASE.parent / "sample_documents"

# Point configuration at a throwaway database + storage directory *before* the app
# imports config values into modules.
_TMP = Path(tempfile.mkdtemp(prefix="veritext-tests-"))
os.environ.setdefault("VERITEXT_STORAGE_DIR", str(_TMP))
os.environ.setdefault("VERITEXT_DB_PATH", str(_TMP / "test.sqlite3"))
os.environ.setdefault("VERITEXT_TEMP_DIR", str(_TMP / "tmp"))
os.environ.setdefault("VERITEXT_LOG_LEVEL", "ERROR")


@pytest.fixture(scope="session")
def sample_pdf_a() -> Path:
    path = SAMPLES / "source_article.pdf"
    if not path.exists():
        pytest.skip("sample PDFs missing — run: python evaluation/make_samples.py")
    return path


@pytest.fixture(scope="session")
def sample_pdf_b() -> Path:
    path = SAMPLES / "student_submission.pdf"
    if not path.exists():
        pytest.skip("sample PDFs missing — run: python evaluation/make_samples.py")
    return path


@pytest.fixture(scope="session")
def sample_docx_b() -> Path:
    path = SAMPLES / "student_submission.docx"
    if not path.exists():
        pytest.skip("sample DOCX missing — run: python evaluation/make_samples.py")
    return path


@pytest.fixture(scope="session")
def app():
    from app import create_app

    application = create_app()
    application.config.update(TESTING=True)
    return application


@pytest.fixture()
def client(app):
    return app.test_client()
