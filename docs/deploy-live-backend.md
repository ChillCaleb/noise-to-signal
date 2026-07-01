# Deploy the Extension Backend

Docker is the package format. A host such as Google Cloud Run, Render, Fly.io, or Hugging Face Spaces is the live service.

For this project, the lowest-friction production-ish path is:

1. Run the Chrome extension locally in Chrome.
2. Deploy the FastAPI backend as a public HTTPS service.
3. Store `GROQ_API_KEY` on the host, never in the extension.
4. Set `EXTENSION_API_TOKEN` on the host and paste the same token into the extension.

## Recommended: Google Cloud Run

Cloud Run is a good fit because it runs Docker containers, gives you HTTPS, and can scale to zero. You still need a Google Cloud billing account, but light personal use is usually near-free because Cloud Run has a monthly free tier.

One-time setup:

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com
```

Deploy from the repo root:

```bash
gcloud run deploy noise-to-signal-api \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GROQ_MODEL=llama-3.1-8b-instant \
  --set-env-vars GROQ_API_KEY=YOUR_GROQ_KEY \
  --set-env-vars EXTENSION_API_TOKEN=YOUR_RANDOM_EXTENSION_TOKEN
```

After deploy:

1. Copy the Cloud Run service URL.
2. Paste it into the extension's `Backend` field.
3. Paste `YOUR_RANDOM_EXTENSION_TOKEN` into the extension's `API token` field.
4. Click `Analyze page`.

Use a real random token, for example a long password from your password manager.

## Easier Alternative: Render

Render can deploy this repo from GitHub using the included `Dockerfile`.

Suggested settings:

```text
Type: Web Service
Runtime: Docker
Dockerfile path: ./Dockerfile
Health check path: /health
Environment variables:
  GROQ_API_KEY=...
  GROQ_MODEL=llama-3.1-8b-instant
  EXTENSION_API_TOKEN=...
```

Render is often simpler than Google Cloud, but free services may sleep and can have tighter usage limits. The paid starter tier is usually the "it just stays up" option.

## Cheapest Demo Alternative: Hugging Face Spaces

Hugging Face Spaces has free CPU hardware and supports Docker, but free Spaces sleep when unused. This can work for a demo, but it is not my first choice for a private browser extension backend.

## Keep Costs Down

- Keep `min instances` at `0` on Cloud Run.
- Use request-based billing where possible.
- Do not enable always-on workers.
- Keep the backend protected with `EXTENSION_API_TOKEN`.
- Set a spending/budget alert in the cloud provider.
- Watch Groq usage separately; the cloud host may be cheap while LLM calls cost money.

