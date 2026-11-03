# VeriText AI — Semantic Plagiarism Detector

**Beyond matching words. Understanding meaning.**

VeriText compares two documents and detects exact, near-exact, and
semantic/paraphrase matches using sentence embeddings
(all-MiniLM-L6-v2) and cosine similarity. Built as a Flask backend
with a React frontend.

## Project structure

```
backend/
  app.py               # Flask app + API routes (+ SPA fallback)
  database.py          # SQLite history store
  text_extraction.py   # PDF / DOCX / TXT text extraction
  nlp_engine.py        # Similarity engine (embeddings + TF-IDF fallback)
  pdf_report.py        # Polished 3-page PDF report generator
  requirements.txt     # Python dependencies
  uploads/             # temporary uploads (ignored)
  reports/             # generated JSON/PDF (ignored)
  dist/                # built React frontend (served by Flask)
  venv/                # virtualenv (ignored)
frontend/
  package.json, vite.config.js, tailwind.config.js, postcss.config.js
  index.html
  src/
    main.jsx, index.css, App.jsx
    components/        # DropZone, FileCard, MatchCard, Collapsible, StatCard
    pages/             # UploadPage, ResultPage
```

## Quick start

```bash
# 1. Create and activate the virtualenv
python3 -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows

# 2. Install Python dependencies
pip install -r backend/requirements.txt

# 3. Build the frontend (served by Flask at /)
cd frontend
npm install
npm run build
cd ..

# 4. Run the server
python backend/app.py
# Open http://localhost:5000
```

No GPU is required. When CUDA is available the embedding model runs on the
GPU automatically; otherwise it falls back to CPU, and when the model hub is
unreachable a TF-IDF cosine similarity is used instead.

## API

- `GET /api/health` — server status + device
- `POST /api/analyze` — multipart `file_a` + `file_b` → analysis result
- `GET /api/result/<id>` — full analysis result
- `GET /api/result/<id>/json` — download machine-readable JSON
- `GET /api/result/<id>/pdf` — download the 3-page PDF report
- `GET /api/history` — recent analyses

## Design

The UI follows a strict visual hierarchy:

1. **Demo / most important** — similarity score, matches, evidence
2. **User information** — coverage, other matches, report
3. **Technical information** — embeddings, cosine similarity, thresholds
   (collapsible "How was this calculated?")

PDF is human-focused; JSON is machine-focused. Similarity is never called a
"plagiarism percentage" — similarity does not prove plagiarism; results
should be reviewed by a human.

## Demo story

1. Upload Document A and Document B.
2. Click **Analyze Documents**.
3. Immediately see the similarity score + label.
4. Immediately see the semantic / exact / near-exact match counts.
5. Immediately see the strongest match side by side — "Different wording,
   similar meaning."
6. Explore the other matches, coverage summary, detected passages, and
   technical details.
7. Export the PDF report or JSON result.