# Noise to Signal Chrome Extension

This is a Manifest V3 Chrome extension that analyzes the active article through the local Noise to Signal API.

## 1. Start the backend

From the project root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add `GROQ_API_KEY` to `.env`, then run:

```bash
python -m uvicorn api.server:app --reload --host 0.0.0.0 --port 8000
```

Check:

```bash
curl http://127.0.0.1:8000/health
```

## 2. Load the extension

1. Open `chrome://extensions`.
2. Enable Developer mode.
3. Click Load unpacked.
4. Select this `extension/` folder.
5. Open a news article and click the Noise to Signal toolbar button.

The side panel defaults to `http://127.0.0.1:8000`.

If the backend is running in GitHub Codespaces, forward port `8000` and paste the forwarded `https://...app.github.dev` URL into the extension's Backend field.

## What works now

- Reads the active page text when possible.
- Falls back to sending only the URL so the backend can ingest it.
- Calls `POST /api/analyze`.
- Shows the summary and extracted signals.
- Saves recent analyses in SQLite via the backend.

## Known next steps

- Add authentication before exposing the backend publicly.
- Replace localhost permissions with the production API domain.
- Add extension icons before Chrome Web Store submission.
- Add a privacy policy and Chrome Web Store listing materials.
- Add deeper history detail loading in the side panel.
