"""
Tests for hardware detection and the device-aware embedding path.

These tests assert *honesty* of the reported environment — the API must never
claim a GPU that does not exist — and correctness of the CUDA out-of-memory
policy, which cannot be exercised by allocating real VRAM in CI.
"""

from __future__ import annotations

import numpy as np
import pytest

from services import hardware
from services.embedding_service import EmbeddingService, EmbeddingError, get_embedding_service


# --------------------------------------------------------------------- hardware
def test_describe_reports_required_fields():
    info = hardware.describe()
    for key in ("python", "torch", "cuda", "device", "gpu", "batch", "platform", "notes"):
        assert key in info

    assert info["device"]["resolved"] in {"cuda", "cpu", "mps"}
    assert info["device"]["requested"] == hardware.Config.DEVICE
    assert isinstance(info["cuda"]["available"], bool)
    assert isinstance(info["batch"]["effective"], int) and info["batch"]["effective"] >= 1
    assert isinstance(info["notes"], list)


def test_gpu_fields_are_not_fabricated():
    """When CUDA is unavailable the GPU block must be empty, not invented."""
    info = hardware.describe()
    if not info["cuda"]["available"]:
        assert info["gpu"]["name"] is None
        assert info["gpu"]["total_vram_mb"] is None
        assert info["gpu"]["free_vram_mb"] is None
        assert info["device"]["resolved"] != "cuda"
    else:  # pragma: no cover - only on a CUDA machine
        assert isinstance(info["gpu"]["name"], str) and info["gpu"]["name"]
        assert info["gpu"]["total_vram_mb"] > 0


def test_forced_cuda_degrades_to_cpu_with_a_note(monkeypatch):
    import torch

    monkeypatch.setattr(hardware.Config, "DEVICE", "cuda")
    hardware.describe.cache_clear()
    try:
        info = hardware.describe()
        if not torch.cuda.is_available():
            assert info["device"]["resolved"] == "cpu"
            assert any("VERITEXT_DEVICE=cuda" in note for note in info["notes"])
    finally:
        monkeypatch.undo()
        hardware.describe.cache_clear()


def test_batch_size_defaults_follow_the_device():
    gpu_batch = hardware.resolve_batch_size("cuda")
    cpu_batch = hardware.resolve_batch_size("cpu")
    assert gpu_batch >= 1 and cpu_batch >= 1
    if not hardware.Config.EMBEDDING_BATCH_SIZE:
        assert gpu_batch == hardware.Config.EMBEDDING_BATCH_GPU == 16
        assert cpu_batch == hardware.Config.EMBEDDING_BATCH_CPU


def test_explicit_batch_override_wins(monkeypatch):
    monkeypatch.setattr(hardware.Config, "EMBEDDING_BATCH_SIZE", 7)
    assert hardware.resolve_batch_size("cuda") == 7
    assert hardware.resolve_batch_size("cpu") == 7


# ------------------------------------------------------------ embedding service
def test_service_uses_the_resolved_device():
    service = get_embedding_service()
    assert service.load() is True
    status = service.status()
    assert status["device"] == hardware.resolved_device()
    assert status["cuda_available"] == hardware.describe()["cuda"]["available"]
    assert status["batch_size"] == hardware.resolve_batch_size(status["device"])
    assert status["loaded"] is True
    assert status["dimension"] == 384
    assert status["torch_version"]


def test_encode_returns_unit_vectors():
    service = get_embedding_service()
    matrix = service.encode(
        ["Machine translation has improved rapidly.", "Neural models translate text well."],
        use_cache=False,
    )
    assert matrix.shape == (2, 384)
    norms = np.linalg.norm(matrix, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-5)


def test_oom_halves_the_batch_and_retries(monkeypatch):
    """A CUDA OOM at a large batch must be retried at a smaller batch, not raised."""
    service = get_embedding_service()
    assert service.load() is True
    original = service._model.encode
    calls = []

    def fake_encode(texts, batch_size=32, **kwargs):
        calls.append(batch_size)
        if batch_size > 4:
            raise RuntimeError("CUDA out of memory. Tried to allocate 512.00 MiB")
        return original(texts, batch_size=batch_size, **kwargs)

    monkeypatch.setattr(service._model, "encode", fake_encode)
    try:
        vectors = service.encode(
            [f"Sentence number {i} about academic writing." for i in range(10)],
            use_cache=False,
        )
    finally:
        monkeypatch.undo()

    assert vectors.shape == (10, 384)
    assert len(calls) >= 2, "the encoder should have been retried"
    assert calls[-1] <= 4, f"batch was never reduced: {calls}"
    assert service.status()["oom_events"] >= 1


def test_oom_when_a_single_sentence_fits_only_after_cpu_fallback(monkeypatch):
    """With batch already 1, an OOM on CUDA switches the session to CPU."""
    service = get_embedding_service()
    assert service.load() is True
    monkeypatch.setattr(service, "_device", "cuda")       # pretend we are on the GPU
    monkeypatch.setattr(service, "_batch_size", 1)

    original = service._model.encode
    state = {"failed": False}

    def fake_encode(texts, batch_size=1, **kwargs):
        if not state["failed"]:
            state["failed"] = True
            raise RuntimeError("CUDA out of memory. Tried to allocate 20.00 MiB")
        return original(texts, batch_size=batch_size, **kwargs)

    monkeypatch.setattr(service._model, "encode", fake_encode)
    try:
        vectors = service.encode(["A single sentence that must still be encoded."], use_cache=False)
        assert vectors.shape == (1, 384)
        assert service.device == "cpu"
        assert "CPU" in (service.status()["fallback_reason"] or "")
    finally:
        monkeypatch.undo()
        service._device = hardware.resolved_device()
        service._batch_size = hardware.resolve_batch_size(service._device)
        service._fallback_reason = None


def test_oom_message_is_actionable_when_fallback_disabled(monkeypatch):
    service = get_embedding_service()
    assert service.load() is True
    monkeypatch.setattr(service, "_device", "cuda")
    monkeypatch.setattr(service, "_batch_size", 1)
    monkeypatch.setattr(hardware.Config, "CUDA_OOM_CPU_FALLBACK", False)

    def always_oom(texts, batch_size=1, **kwargs):
        raise RuntimeError("CUDA out of memory. Tried to allocate 20.00 MiB")

    monkeypatch.setattr(service._model, "encode", always_oom)
    try:
        with pytest.raises(EmbeddingError) as excinfo:
            service.encode(["Text that cannot be encoded on the GPU."], use_cache=False)
        message = str(excinfo.value)
        assert "out of memory" in message.lower()
        assert "VERITEXT_DEVICE=cpu" in message
    finally:
        monkeypatch.undo()
        service._device = hardware.resolved_device()
        service._batch_size = hardware.resolve_batch_size(service._device)


def test_missing_model_error_is_explicit():
    """A load failure must produce an explanation, never silent fake vectors."""
    service = EmbeddingService(model_name="sentence-transformers/this-model-does-not-exist-xyz")
    assert service.load() is False
    status = service.status()
    assert status["loaded"] is False
    assert status["error"]
    with pytest.raises(EmbeddingError):
        service.encode(["This must not silently succeed."])


def test_compare_returns_explicit_error_when_model_is_unavailable(client, sample_pdf_a, sample_pdf_b):
    """No model => HTTP 503 with an actionable message, never fabricated scores."""
    import io

    from services.embedding_service import get_embedding_service

    service = get_embedding_service()

    def upload(path, label):
        with path.open("rb") as handle:
            response = client.post(
                "/api/documents/upload",
                data={"file": (io.BytesIO(handle.read()), path.name), "label": label},
                content_type="multipart/form-data",
            )
        assert response.status_code == 201
        return response.get_json()["data"]["document_id"]

    doc_a = upload(sample_pdf_a, "A")
    doc_b = upload(sample_pdf_b, "B")

    model, error, kind = service._model, service._load_error, service._load_error_kind
    service._model = None
    service._load_error = "LocalEntryNotFoundError: offline"
    service._load_error_kind = "model_download_failed"
    service.load = lambda blocking=True: False  # simulate an unreachable model
    try:
        response = client.post(
            "/api/analysis/compare", json={"doc_a_id": doc_a, "doc_b_id": doc_b}
        )
        assert response.status_code == 503
        body = response.get_json()
        assert body["success"] is False
        assert body["error"]["code"] == "embedding_unavailable"
        assert "model" in body["error"]["message"].lower()
        assert "hint" in body["error"]
    finally:
        service._model = model
        service._load_error = error
        service._load_error_kind = kind
        del service.load        # restore the bound method from the class


def test_health_endpoint_reports_runtime(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.get_json()["data"]

    assert data["status"] in {"ok", "loading", "model_unavailable"}
    runtime = data["runtime"]
    assert runtime["device"]["resolved"] in {"cuda", "cpu", "mps"}
    assert runtime["device"]["resolved"] == data["model"]["device"]
    assert runtime["batch"]["effective"] == data["model"]["batch_size"]
    assert data["model"]["model"]
    assert data["model"]["dimension"] == 384
    assert data["limits"]["max_upload_mb"] >= 1
    assert data["limits"]["max_sentences_per_document"] >= 1
    assert "python" in runtime and runtime["python"]["version"]
    # No fabricated GPU data when CUDA is unavailable.
    if not runtime["cuda"]["available"]:
        assert runtime["gpu"]["name"] is None
