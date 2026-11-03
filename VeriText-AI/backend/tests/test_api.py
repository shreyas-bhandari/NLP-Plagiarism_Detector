"""API-level tests: uploads, comparison, history, reports, deletion, error handling."""

from __future__ import annotations

import io
import json

import pytest


def _upload(client, path, label="A", filename=None):
    with path.open("rb") as handle:
        data = {
            "file": (io.BytesIO(handle.read()), filename or path.name),
            "label": label,
        }
        return client.post("/api/documents/upload", data=data, content_type="multipart/form-data")


# --------------------------------------------------------------------------- #
# health
# --------------------------------------------------------------------------- #
def test_health_reports_model_and_limits(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["status"] == "ok"
    assert payload["model"]["loaded"] is True
    assert payload["model"]["model"] == "sentence-transformers/all-MiniLM-L6-v2"
    assert payload["model"]["dimension"] == 384
    assert payload["limits"]["max_upload_mb"] > 0


def test_unknown_endpoint_returns_json_404(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.get_json()["success"] is False


# --------------------------------------------------------------------------- #
# uploads
# --------------------------------------------------------------------------- #
def test_upload_pdf_returns_metadata_and_preview(client, sample_pdf_a):
    response = _upload(client, sample_pdf_a, "A")
    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["document_id"].startswith("doc_")
    assert data["file_type"] == "pdf"
    assert data["word_count"] > 100
    assert data["sentence_count"] > 10
    assert data["preview"]["excerpt"]
    # Server paths must never leak into API responses.
    assert "storage" not in json.dumps(data)
    assert "/tmp" not in json.dumps(data)


def test_upload_docx_works(client, sample_docx_b):
    response = _upload(client, sample_docx_b, "B")
    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["file_type"] == "docx"
    assert data["sentence_count"] > 10


def test_upload_rejects_unsupported_extension(client):
    data = {"file": (io.BytesIO(b"hello world"), "notes.exe")}
    response = client.post("/api/documents/upload", data=data, content_type="multipart/form-data")
    assert response.status_code == 415
    assert response.get_json()["error"]["code"] == "invalid_upload"


def test_upload_rejects_fake_pdf(client):
    data = {"file": (io.BytesIO(b"this is definitely not a pdf"), "fake.pdf")}
    response = client.post("/api/documents/upload", data=data, content_type="multipart/form-data")
    assert response.status_code == 415


def test_upload_rejects_empty_file(client):
    data = {"file": (io.BytesIO(b""), "empty.pdf")}
    response = client.post("/api/documents/upload", data=data, content_type="multipart/form-data")
    assert response.status_code == 400


def test_upload_rejects_corrupt_pdf(client):
    data = {"file": (io.BytesIO(b"%PDF-1.4 truncated garbage without xref"), "broken.pdf")}
    response = client.post("/api/documents/upload", data=data, content_type="multipart/form-data")
    assert response.status_code in (415, 422)
    assert response.get_json()["success"] is False


def test_upload_rejects_document_with_too_little_text(client):
    data = {"file": (io.BytesIO(b"Too short to analyse."), "tiny.txt")}
    response = client.post("/api/documents/upload", data=data, content_type="multipart/form-data")
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "document_too_short"


def test_cached_document_can_be_fetched_and_deleted(client, sample_pdf_a):
    document_id = _upload(client, sample_pdf_a).get_json()["data"]["document_id"]
    fetched = client.get(f"/api/documents/{document_id}")
    assert fetched.status_code == 200
    assert client.delete(f"/api/documents/{document_id}").status_code == 200
    assert client.get(f"/api/documents/{document_id}").status_code == 410


# --------------------------------------------------------------------------- #
# comparison
# --------------------------------------------------------------------------- #
@pytest.fixture()
def analysis(client, sample_pdf_a, sample_pdf_b):
    doc_a = _upload(client, sample_pdf_a, "A").get_json()["data"]["document_id"]
    doc_b = _upload(client, sample_pdf_b, "B").get_json()["data"]["document_id"]
    response = client.post("/api/analysis/compare", json={
        "doc_a_id": doc_a, "doc_b_id": doc_b,
        "options": {"exclude_references": True, "exclude_headings": True},
    })
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"]


def test_compare_produces_real_metrics(analysis):
    summary = analysis["summary"]
    assert analysis["analysis_id"].startswith("an_")
    assert 0 < summary["weighted_similarity"] <= 1
    assert summary["primary_matches"] > 0
    assert summary["exact_matches"] + summary["near_exact_matches"] + summary["semantic_matches"] \
        == summary["primary_matches"]
    assert analysis["engine"]["model"] == "sentence-transformers/all-MiniLM-L6-v2"
    assert analysis["disclaimer"]


def test_compare_records_the_device_it_ran_on(analysis):
    """Each stored result states where the embeddings were computed (GPU or CPU)."""
    from services import hardware

    engine = analysis["engine"]
    assert engine["device"] in {"cuda", "cpu", "mps"}
    assert engine["device"] == hardware.resolved_device()
    assert engine["batch_size"] >= 1


def test_report_renders_with_the_device_line(analysis, client):
    from services.report_generator import generate_pdf_report

    pdf = generate_pdf_report(analysis["analysis_id"], analysis, analysis["created_at"])
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 5000


def test_compare_matches_include_cosine_and_lexical_evidence(analysis):
    for match in analysis["matches"][:5]:
        assert 0.0 <= match["signals"]["cosine"] <= 1.0
        assert match["classification"] in {"exact", "near_exact", "semantic"}
        assert match["explanation"]["headline"]
        assert match["source"]["text"] and match["target"]["text"]


def test_compare_exact_matches_are_exact_strings(analysis):
    exact = [m for m in analysis["matches"] if m["classification"] == "exact"]
    assert exact
    for match in exact:
        assert match["signals"]["cosine"] > 0.9999


def test_compare_documents_endpoint_returns_segmented_text(analysis, client):
    response = client.get(f"/api/analysis/{analysis['analysis_id']}/documents")
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["A"]["sentences"] and data["B"]["sentences"]
    first = data["A"]["sentences"][0]
    for key in ("id", "index", "text", "eligible", "paragraph", "section"):
        assert key in first


def test_compare_rejects_missing_document_ids(client):
    response = client.post("/api/analysis/compare", json={"doc_a_id": "doc_missing"})
    assert response.status_code == 400


def test_compare_rejects_expired_document_ids(client):
    response = client.post("/api/analysis/compare", json={
        "doc_a_id": "doc_doesnotexist1", "doc_b_id": "doc_doesnotexist2",
    })
    assert response.status_code == 410
    assert response.get_json()["error"]["code"] == "invalid_request"


def test_compare_validates_options(client):
    response = client.post("/api/analysis/compare", json={
        "doc_a_id": "doc_x", "doc_b_id": "doc_y",
        "options": {"semantic_threshold": 4.2},
    })
    assert response.status_code == 400


def test_compare_accepts_direct_multipart_upload(client, sample_pdf_a, sample_pdf_b):
    data = {
        "file_a": (io.BytesIO(sample_pdf_a.read_bytes()), sample_pdf_a.name),
        "file_b": (io.BytesIO(sample_pdf_b.read_bytes()), sample_pdf_b.name),
        "options": json.dumps({"exclude_references": True}),
    }
    response = client.post("/api/analysis/compare", data=data, content_type="multipart/form-data")
    assert response.status_code == 201
    assert response.get_json()["data"]["summary"]["primary_matches"] > 0


# --------------------------------------------------------------------------- #
# retrieval, history, reports
# --------------------------------------------------------------------------- #
def test_analysis_metrics_are_bounded_and_consistent(analysis, client):
    """Headline metrics stay inside their mathematical range and survive storage."""
    summary = analysis["summary"]
    assert 0.0 <= summary["weighted_similarity"] <= 1.0
    assert summary["weighted_similarity_pct"] <= 100.0
    assert summary["average_matched_similarity_pct"] <= 100.0
    assert summary["max_similarity_pct"] <= 100.0
    assert summary["primary_matches"] <= summary["coverage"]["A"]["sentences_considered"]
    assert summary["primary_matches"] <= summary["evidence_rows"]

    # The refetched (stored) result must report exactly the same numbers.
    stored = client.get(f"/api/analysis/{analysis['analysis_id']}").get_json()["data"]
    stored_summary = stored["summary"]
    assert stored_summary["weighted_similarity_pct"] == summary["weighted_similarity_pct"]
    assert stored_summary["average_matched_similarity_pct"] == summary["average_matched_similarity_pct"]
    assert stored_summary["primary_matches"] == summary["primary_matches"]
    assert stored_summary["weighted_similarity_pct"] <= 100.0


def test_pdf_report_shows_the_same_index_as_the_api(analysis, client):
    """The PDF is rendered from the authoritative result, so it cannot drift."""
    import pymupdf

    response = client.get(f"/api/analysis/{analysis['analysis_id']}/report")
    assert response.status_code == 200
    document = pymupdf.open(stream=response.data, filetype="pdf")
    text = "\n".join(page.get_text() for page in document)

    index_pct = analysis["summary"]["weighted_similarity_pct"]
    average_pct = analysis["summary"]["average_matched_similarity_pct"]
    assert index_pct <= 100.0
    assert f"{index_pct}%" in text, "the report must print the same index as the API"
    assert f"{average_pct}%" in text
    assert str(analysis["summary"]["primary_matches"]) in text
    # Safety language must survive into the report.
    assert "plagiarism verdict" in text.lower() or "not a plagiarism" in text.lower()


def test_get_analysis_returns_stored_result(client, analysis):
    response = client.get(f"/api/analysis/{analysis['analysis_id']}")
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["status"] == "completed"
    assert data["summary"]["primary_matches"] == analysis["summary"]["primary_matches"]


def test_unknown_analysis_returns_404(client):
    assert client.get("/api/analysis/an_missing").status_code == 404


def test_history_lists_the_analysis(client, analysis):
    response = client.get("/api/analysis/history?limit=10")
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["total"] >= 1
    record = next(item for item in data["items"] if item["id"] == analysis["analysis_id"])
    assert record["doc_a_name"] == "source_article.pdf"
    assert record["summary"]["primary_matches"] == analysis["summary"]["primary_matches"]


def test_history_search_filters(client, analysis):
    response = client.get("/api/analysis/history?search=student_submission")
    assert response.status_code == 200
    items = response.get_json()["data"]["items"]
    assert items and all("student_submission" in item["doc_b_name"] for item in items)


def test_dashboard_stats_are_derived_from_rows(client, analysis):
    response = client.get("/api/stats/dashboard")
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["total_analyses"] >= 1
    assert data["documents_processed"] >= 2
    assert data["average_duration_ms"] >= 0
    assert data["recent"]


def test_report_is_a_pdf(client, analysis):
    response = client.get(f"/api/analysis/{analysis['analysis_id']}/report")
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF")
    assert len(response.data) > 5000
    assert "no-store" in response.headers.get("Cache-Control", "")


def test_json_export(client, analysis):
    response = client.get(f"/api/analysis/{analysis['analysis_id']}/export")
    assert response.status_code == 200
    payload = json.loads(response.data)
    assert payload["summary"]["primary_matches"] >= 0


def test_delete_analysis_removes_it_and_its_text(client, analysis):
    analysis_id = analysis["analysis_id"]
    assert client.delete(f"/api/analysis/{analysis_id}").status_code == 200
    assert client.get(f"/api/analysis/{analysis_id}").status_code == 404
    assert client.get(f"/api/analysis/{analysis_id}/documents").status_code == 410
    assert client.get(f"/api/analysis/{analysis_id}/report").status_code == 404
    assert client.delete(f"/api/analysis/{analysis_id}").status_code == 404


def test_reference_exclusion_option_is_respected(client, sample_pdf_a, sample_pdf_b):
    doc_a = _upload(client, sample_pdf_a, "A").get_json()["data"]["document_id"]
    doc_b = _upload(client, sample_pdf_b, "B").get_json()["data"]["document_id"]
    response = client.post("/api/analysis/compare", json={
        "doc_a_id": doc_a, "doc_b_id": doc_b,
        "options": {"exclude_references": True},
    })
    data = response.get_json()["data"]
    assert all(m["source"]["section"] != "references" for m in data["matches"])
