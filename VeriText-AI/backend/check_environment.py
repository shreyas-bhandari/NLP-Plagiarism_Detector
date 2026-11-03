"""
VeriText AI — environment verification.

Run this before starting the backend, and whenever an analysis behaves oddly:

    python check_environment.py            # full check (loads the model)
    python check_environment.py --no-model # skip the model load / smoke test

It verifies, from the real process rather than from documentation:

    1. Python version
    2. PyTorch version and whether that build contains CUDA
    3. CUDA availability and the detected GPU (name, VRAM)
    4. The device the engine will actually use, and why
    5. Whether the Sentence Transformer model is in the local cache
    6. An end-to-end encode + cosine smoke test

Exit code 0 means the NLP engine is ready. Exit code 1 means analyses would fail —
the reason is printed, and nothing else is faked to hide it.
"""

from __future__ import annotations

import argparse
import sys

from config import Config
from services import hardware

PASS, FAIL, INFO = "[ ok ]", "[FAIL]", "[info]"


def _line(status: str, label: str, value: str = "") -> None:
    print(f"{status} {label:<26} {value}".rstrip())


def check_model_cached(model_name: str) -> tuple[bool, str]:
    """Is the model already in the Hugging Face cache? (no network, no download)"""
    try:
        from huggingface_hub import snapshot_download

        path = snapshot_download(model_name, local_files_only=True)
        return True, path
    except Exception as exc:  # not cached, or hub unavailable offline
        return False, f"not cached locally ({type(exc).__name__})"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the VeriText AI environment.")
    parser.add_argument("--no-model", action="store_true", help="skip loading the model")
    args = parser.parse_args()

    runtime = hardware.describe()
    failures = 0

    print("\nVeriText AI — environment check")
    print("=" * 72)

    # 1 ------------------------------------------------------------------ Python
    python = runtime["python"]
    if python["supported"]:
        _line(PASS, "Python", f"{python['version']} ({python['implementation']})")
    else:
        failures += 1
        _line(FAIL, "Python", f"{python['version']} — need {python['recommended']}")

    # 2/3 -------------------------------------------------------- torch and CUDA
    torch_info = runtime["torch"]
    if torch_info["available"]:
        _line(PASS, "PyTorch", str(torch_info["version"]))
    else:
        failures += 1
        _line(FAIL, "PyTorch", torch_info["error"] or "not installed")

    if torch_info["cuda_build"]:
        _line(INFO, "CUDA build in torch", str(torch_info["cuda_build"]))
    else:
        _line(INFO, "CUDA build in torch", "none (CPU-only wheel)")
    if torch_info["cudnn_version"]:
        _line(INFO, "cuDNN", str(torch_info["cudnn_version"]))

    cuda = runtime["cuda"]
    _line(
        PASS if cuda["available"] else INFO,
        "CUDA available",
        f"{'yes' if cuda['available'] else 'no'} ({cuda['device_count']} device(s))",
    )
    gpu = runtime["gpu"]
    if gpu["name"]:
        _line(
            PASS,
            "GPU",
            f"{gpu['name']} · {gpu['total_vram_mb']} MB VRAM · "
            f"{gpu['free_vram_mb']} MB free · compute {gpu['compute_capability']}",
        )
    else:
        _line(INFO, "GPU", "none detected")

    # 4 ------------------------------------------------------------- resolution
    device = runtime["device"]
    _line(
        PASS,
        "Inference device",
        f"{device['resolved']} (requested: {device['requested']})"
        + (f" · {gpu['name']}" if device["resolved"] == "cuda" else ""),
    )
    _line(INFO, "Embedding batch size", str(runtime["batch"]["effective"]))
    for note in runtime["notes"]:
        _line(INFO, "Note", note)

    # 5 ----------------------------------------------------------- model cache
    cached, location = check_model_cached(Config.MODEL_NAME)
    if cached:
        _line(PASS, "Model in HF cache", location)
    else:
        _line(INFO, "Model in HF cache", location + " — will download on first use")

    # 6 ------------------------------------------------------------- smoke test
    if not args.no_model:
        print("-" * 72)
        try:
            from sentence_transformers import SentenceTransformer  # noqa: F401

            from services.embedding_service import get_embedding_service

            embedder = get_embedding_service()
            if not embedder.load():
                failures += 1
                status = embedder.status()
                _line(FAIL, "Model load", str(status.get("error_kind") or "failed"))
                print(f"\n{embedder.status().get('error')}\n")
                print(embedder.load_error_message())  # actionable, user-facing message
                return 1

            status = embedder.status()
            _line(PASS, "Model loaded", f"{status['model']} ({status['dimension']}-d)")
            _line(PASS, "Device in use", f"{status['device']} · batch {status['batch_size']}")

            import numpy as np

            a, b, c = embedder.encode(
                [
                    "String matching fails when authors paraphrase their sources.",
                    "Rewritten text defeats character n-gram comparison.",
                    "Photosynthesis converts light energy into chemical energy.",
                ],
                use_cache=False,
            )
            paraphrase = float(np.dot(a, b))
            unrelated = float(np.dot(a, c))
            _line(PASS, "Encoding", "3 sentences encoded")
            _line(
                PASS if paraphrase > unrelated else FAIL,
                "Cosine smoke test",
                f"paraphrase={paraphrase:.3f} vs unrelated={unrelated:.3f}",
            )
            if paraphrase <= unrelated:
                failures += 1
        except Exception as exc:
            failures += 1
            _line(FAIL, "Smoke test", f"{type(exc).__name__}: {exc}")

    print("=" * 72)
    if failures:
        print(f"{FAIL} {failures} problem(s) found — the NLP engine is NOT ready.")
        print("See docs/INSTALL_WINDOWS.md for the Windows/Conda setup.")
        return 1
    print(f"{PASS} Environment looks good. Start the backend with: python app.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
