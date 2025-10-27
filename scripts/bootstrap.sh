#!/usr/bin/env bash
set -euo pipefail

# repo root
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON="${PYTHON:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"

# Create venv inside the repo if missing
if [ ! -d "$VENV_DIR" ]; then
  $PYTHON -m venv "$VENV_DIR"
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# Upgrade pip + install deps
python -m pip install --upgrade pip
pip install -r requirements.txt

# Ensure spaCy model is present
python - <<'PY'
import importlib, subprocess, sys
try:
    import en_core_web_sm  # noqa: F401
except Exception:
    subprocess.check_call([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
PY

echo "✅ Environment ready in $VENV_DIR"
echo "To run the app: source $VENV_DIR/bin/activate && streamlit run app/Home.py"
