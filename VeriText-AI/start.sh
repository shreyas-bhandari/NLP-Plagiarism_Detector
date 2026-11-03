#!/usr/bin/env bash
#
# VeriText AI — convenience launcher (single origin).
#
#   ./start.sh
#
# Builds the React frontend on first run, then starts Flask, which serves both the
# API and the built SPA on http://localhost:5000.
#
# For frontend development with hot reload use two terminals instead:
#   cd backend  && python app.py
#   cd frontend && npm run dev        # http://localhost:5173, proxies /api
#
# Windows: this script needs bash. Use PowerShell instead —
#   powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
#   cd backend; python check_environment.py; python app.py
# Full guide: docs/INSTALL_WINDOWS.md
#
set -euo pipefail
cd "$(dirname "$0")"

command -v python3 >/dev/null || { echo "python3 is required"; exit 1; }

python3 -c "import torch" 2>/dev/null || {
  echo "PyTorch is missing. Install the wheel that matches your GPU/driver first, e.g.:"
  echo "  pip install torch --index-url https://download.pytorch.org/whl/cu124"
  echo "  pip install -r backend/requirements.txt"
  echo "(CPU-only machines: use https://download.pytorch.org/whl/cpu — the app falls back to CPU)"
  exit 1
}

# Print the detected runtime (device, CUDA, GPU, batch size) before starting.
(cd backend && python3 check_environment.py --no-model || true)

if [ ! -d frontend/node_modules ]; then
  echo "Installing frontend dependencies…"
  (cd frontend && npm install --no-audit --no-fund)
fi

if [ ! -f frontend/dist/index.html ]; then
  echo "Building frontend…"
  (cd frontend && npm run build)
fi

echo "Starting VeriText AI on http://localhost:${VERITEXT_PORT:-5000}"
cd backend
exec python3 app.py
