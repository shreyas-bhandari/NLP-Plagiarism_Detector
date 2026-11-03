# Installing VeriText AI on Windows (PowerShell + Conda + NVIDIA GPU)

Target machine for these instructions: **Windows 10/11**, **NVIDIA GeForce RTX 3050 Laptop GPU
(4 GB VRAM)**, CPU-only fallback always available. Every command below is PowerShell. Nothing here
touches your other Conda environments, and nothing forces a CPU-only PyTorch install.

> The engine detects its device at runtime. If CUDA is available it uses the GPU; if not, it runs on
> the CPU and says so in `GET /api/health`, in the sidebar badge and in `python check_environment.py`.
> No code change is needed to switch between them.

---

## 0. Prerequisites (once)

| Requirement | Check |
|---|---|
| NVIDIA driver installed | `nvidia-smi` — shows the GPU name, driver version and the *maximum* CUDA version your driver supports |
| Miniconda / Anaconda | `conda --version` |
| Node.js 18+ | `node -v` and `npm -v` |
| ~5 GB free disk | PyTorch (CUDA build ≈ 2.5 GB), the model (~90 MB), Node modules |

If `conda` is not recognised in PowerShell, run `conda init powershell` once and open a new window.

```
nvidia-smi
```

Sample (your versions will differ):

```
+-----------------------------------------------------------------------------+
| NVIDIA-SMI 551.86    Driver Version: 551.86    CUDA Version: 12.4           |
|   0  NVIDIA GeForce RTX 3050 Laptop GPU      WDDM  | 4096MiB / 4096MiB      |
+-----------------------------------------------------------------------------+
```

The "CUDA Version" in `nvidia-smi` is the **newest CUDA runtime your driver can run**. Pick a PyTorch
wheel whose CUDA version is ≤ that number.

---

## 1. Create a dedicated Conda environment

A separate environment keeps VeriText's PyTorch/Transformers stack away from your other projects.

```powershell
conda create -n veritext python=3.11 -y
conda activate veritext
python -V
```

`python -V` should print `Python 3.11.x`. Python 3.11 or 3.12 is recommended (3.10+ works).

To leave it later: `conda deactivate`. To remove it completely: `conda env remove -n veritext`.

---

## 2. Install CUDA-enabled PyTorch

**Do not install the CPU-only wheel.** The CUDA wheel comes from PyTorch's own index, not from PyPI.

Choose the command that matches your driver from <https://pytorch.org/get-started/locally/>
(the selector on that page is always current). Typical current options:

```powershell
# CUDA 12.4 build
pip install torch --index-url https://download.pytorch.org/whl/cu124

# or CUDA 12.1 build (older drivers)
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

Verify the install — this is the only check that matters:

```powershell
python -c "import torch; print('torch', torch.__version__); print('cuda build', torch.version.cuda); print('available', torch.cuda.is_available()); print('gpu', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')"
```

Expected on the RTX 3050:

```
torch 2.x.x+cu124
cuda build 12.4
available True
gpu NVIDIA GeForce RTX 3050 Laptop GPU
```

If `available` is `False`, see [Troubleshooting](#7-troubleshooting) — do not continue with a broken
CUDA install and expect the backend to fix it.

### Already have a working CUDA Conda environment?

Then **reuse it** and skip the install. Only verify and install the remaining dependencies:

```powershell
conda env list                     # find the environment you already use for PyTorch
conda activate <your-env-name>
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
pip show torch                     # confirm the build (should contain +cuXXX)
```

If that prints `available True`, continue to step 3. `requirements.txt` deliberately does **not**
list `torch`, so `pip install -r requirements.txt` will keep the CUDA build you already have rather
than replacing it with a CPU wheel.

> Cloning instead of reusing? `conda create -n veritext --clone <your-env>` copies the working CUDA
> stack into a new environment, at the cost of disk space.

---

## 3. Install the backend dependencies

```powershell
cd VeriText-AI\backend
pip install -r requirements.txt
```

This installs Flask, sentence-transformers, transformers, scikit-learn, NumPy, Pandas, PyMuPDF,
python-docx, NLTK and ReportLab. PyTorch is untouched.

Confirm that pip did not swap your GPU build:

```powershell
pip show torch | Select-String -Pattern "Version"
```

The version must still contain `+cu`. If it does not, reinstall the CUDA wheel (step 2).

For the test suite as well:

```powershell
pip install -r requirements-dev.txt
```

---

## 4. Verify the environment before running anything

```powershell
python check_environment.py
```

Expected output on the RTX 3050:

```
VeriText AI — environment check
========================================================================
[ ok ] Python                     3.11.x (CPython)
[ ok ] PyTorch                    2.x.x+cu124
[info] CUDA build in torch        12.4
[ ok ] CUDA available             yes (1 device(s))
[ ok ] GPU                        NVIDIA GeForce RTX 3050 Laptop GPU · 4096 MB VRAM · … MB free · compute 8.6
[ ok ] Inference device           cuda (requested: auto) · NVIDIA GeForce RTX 3050 Laptop GPU
[info] Embedding batch size       16
[ ok ] Model in HF cache          C:\Users\<you>\.cache\huggingface\hub\models--sentence-transformers--all-MiniLM-L6-v2\snapshots\…
[ ok ] Model loaded               sentence-transformers/all-MiniLM-L6-v2 (384-d)
[ ok ] Device in use              cuda · batch 16
[ ok ] Cosine smoke test          paraphrase=0.7xx vs unrelated=0.0xx
========================================================================
[ ok ] Environment looks good. Start the backend with: python app.py
```

On a machine without CUDA you will see `device=cpu`, `batch 32` and an explicit note explaining which
wheel is installed — that is the CPU fallback working as intended, not an error.

The first run downloads the model (~90 MB) from Hugging Face. After that it is loaded from the local
cache and no network is needed (`VERITEXT_MODEL_LOCAL_ONLY=true` makes that strict).

---

## 5. Frontend

```powershell
cd ..\frontend
npm install
```

Two ways to run:

**A. Single origin (recommended, one server)** — build the React bundle, then start Flask, which
serves both the API and the built app on port 5000:

```powershell
npm run build
cd ..\backend
python app.py
# open http://localhost:5000
```

**B. Development with hot reload** — two PowerShell windows:

```powershell
# window 1
cd VeriText-AI\backend
conda activate veritext
python app.py                 # API on http://localhost:5000

# window 2
cd VeriText-AI\frontend
npm run dev                   # UI on http://localhost:5173 (proxies /api to 5000)
```

---

## 6. Tests, evaluation, and reports

```powershell
# backend test suite (80 tests)
cd VeriText-AI\backend
conda activate veritext
python -m pytest tests -q

# measured NLP evaluation — writes docs\evaluation_results.md and .json
python evaluation\evaluate.py --markdown --json

# regenerate the sample PDF/DOCX pair used in the demo
python evaluation\make_samples.py
```

The evaluation numbers in the README and in `docs/evaluation_results.md` come from running that
script; they are not constants typed into the documentation.

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `torch.cuda.is_available()` is `False` | CPU-only wheel installed, or driver too old | `python -c "import torch; print(torch.version.cuda)"` → `None` means CPU wheel: reinstall from `--index-url .../cuXXX`. Still `False` with a `+cu` build → update the NVIDIA driver, reboot, check `nvidia-smi` |
| `DLL load failed while importing torch` (`c10.dll`, `fbgemm.dll`) | Mixed conda/pip torch installs, or missing MSVC runtime | Create a fresh env, install torch **once** with pip, install the [Microsoft VC++ redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) |
| `pip install -r requirements.txt` replaced my CUDA torch with CPU torch | Another package pinned an incompatible torch | Reinstall the CUDA wheel afterwards, and check `pip list` for stray `torch` pins |
| `CUDA out of memory` during analysis | 4 GB VRAM is shared with the desktop/browser | Set `$env:VERITEXT_EMBED_BATCH = "8"`, close GPU-heavy apps, or `$env:VERITEXT_DEVICE = "cpu"`. The engine already halves the batch automatically and falls back to CPU if needed |
| `Couldn't connect to huggingface.co` / `LocalEntryNotFoundError` | First run without internet | Connect once so the model is cached (or copy `%USERPROFILE%\.cache\huggingface` from another machine). Afterwards you can set `HF_HUB_OFFLINE=1` and `VERITEXT_MODEL_LOCAL_ONLY=true` |
| `conda activate` does nothing in PowerShell | Shell not initialised | `conda init powershell`, reopen the terminal |
| `WinError 10013` / port 5000 busy | Another process owns the port | `netstat -ano \| findstr :5000` then `taskkill /PID <pid> /F`, or `$env:VERITEXT_PORT = "5001"` |
| Very slow first analysis | Model load + CUDA kernel warm-up | The backend loads and warms up the model at startup on purpose; the first comparison is then fast |
| `npm run build` fails on a path with spaces | npm/Windows path handling | Clone into a path without spaces, e.g. `C:\projects\VeriText-AI` |

### Watching GPU usage while analysing

```powershell
nvidia-smi -l 1
```

`python check_environment.py` and `GET /api/health` report `free_vram_mb`, so you can see the
headroom an analysis actually had.

---

## 8. Command cheat sheet

```powershell
conda activate veritext
cd C:\projects\VeriText-AI\backend
python check_environment.py            # verify python / torch / CUDA / GPU / model
python app.py                          # API + built UI on http://localhost:5000
python -m pytest tests -q               # 80 tests
python evaluation\evaluate.py --markdown --json

cd ..\frontend
npm install
npm run build                          # for the single-origin Flask deployment
npm run dev                            # or: hot-reload UI on http://localhost:5173
```

---

## 9. GPU vs CPU — expectations, honestly

- Embedding is a single forward pass per sentence; the MiniLM encoder is small (6 layers, 384 dims).
  On the CPU used for development, a full two-document comparison (≈110 sentences) takes
  **≈0.2–0.3 s** end to end, so CPU is not a bottleneck at this document size.
- On a 4 GB RTX 3050 the GPU usually wins on larger documents, but for short documents the
  transfer/synchronisation overhead can make the difference small — measurements from this
  repository's development sandbox are CPU-only, so **no GPU speed-up figure is claimed here**.
  Measure on your own machine with the timings returned by `POST /api/analysis/compare`
  (`engine.timings`) before assuming a gain.
- Memory is bounded either way: batches of 16 on GPU, and the cosine search is evaluated in row
  blocks so the full sentence-by-sentence matrix is never materialised.
