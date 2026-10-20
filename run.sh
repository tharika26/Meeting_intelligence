#!/usr/bin/env bash
# Sets up and runs the backend with demo data seeded.
set -e
cd "$(dirname "$0")/backend"
python -m venv .venv 2>/dev/null || true
source .venv/bin/activate 2>/dev/null || true
pip install -q -r requirements.txt
python seed_data.py
echo ""
echo "Starting API at http://localhost:8000 (docs at /docs)"
echo "Open frontend/index.html in your browser (or 'python -m http.server 5500' inside frontend/)"
echo ""
uvicorn app.main:app --reload --port 8000
