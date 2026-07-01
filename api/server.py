from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from adapter_input import to_document
from main import build_document_from_url, run_llm, run_nlp

from .models import AnalyzeRequest, AnalyzeResponse, HistoryResponse
from .storage import get_run, init_db, list_runs, save_run


load_dotenv()

app = FastAPI(
    title="Noise to Signal API",
    version="0.1.0",
    description="Local API used by the Noise to Signal Chrome extension.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _clean_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _build_document(payload: AnalyzeRequest) -> Dict[str, Any]:
    text = _clean_optional(payload.text)
    title = _clean_optional(payload.title)
    url = _clean_optional(payload.url)
    if text:
        return to_document(text=text, title=title, url=url)
    if not url:
        raise HTTPException(status_code=400, detail="Provide either text or url.")
    return build_document_from_url(url)


def _pipeline_error(exc: Exception) -> HTTPException:
    message = str(exc)
    if "GROQ_API_KEY" in message:
        return HTTPException(
            status_code=503,
            detail="GROQ_API_KEY is missing on the backend. Add it to .env before analyzing.",
        )
    return HTTPException(status_code=500, detail=f"Analysis failed: {message}")


def require_extension_token(request: Request) -> None:
    expected = os.getenv("EXTENSION_API_TOKEN")
    if not expected:
        return
    provided = request.headers.get("X-Noise-Signal-Key")
    if provided != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing extension API token.")


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "noise-to-signal-api",
        "db": str(os.getenv("NOISE_SIGNAL_DB") or "data/noise_to_signal_extension.db"),
        "groq_configured": bool(os.getenv("GROQ_API_KEY")),
    }


@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "noise-to-signal-api",
        "message": "Use /health to check status or /api/analyze from the Chrome extension.",
    }


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest, _: None = Depends(require_extension_token)) -> AnalyzeResponse:
    run_id = str(uuid4())
    created_at = _now_iso()

    try:
        document = _build_document(payload)
        analysis = run_nlp(document)
        summary_text = run_llm(
            analysis,
            tier=payload.tier,
            output_format=payload.output_format,
            length=payload.length,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise _pipeline_error(exc) from exc

    doc_meta = document.get("meta") or {}
    title = _clean_optional(payload.title) or doc_meta.get("title")
    url = _clean_optional(payload.url) or doc_meta.get("url")
    input_text = (document.get("content") or {}).get("text") or ""
    model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    source_type = "text" if _clean_optional(payload.text) else "url"

    if payload.save:
        save_run(
            run_id=run_id,
            created_at=created_at,
            title=title,
            url=url,
            input_text=input_text,
            document=document,
            analysis=analysis,
            summary_text=summary_text,
            tier=payload.tier,
            output_format=payload.output_format,
            length=payload.length,
            model=model,
            source_type=source_type,
        )

    return AnalyzeResponse(
        id=run_id,
        created_at=created_at,
        title=title,
        url=url,
        summary_text=summary_text,
        analysis=analysis,
        meta={
            "tier": payload.tier,
            "output_format": payload.output_format,
            "length": payload.length,
            "model": model,
            "source_type": source_type,
            "saved": payload.save,
        },
    )


@app.get("/api/history", response_model=HistoryResponse)
def history(
    limit: int = Query(default=25, ge=1, le=100),
    _: None = Depends(require_extension_token),
) -> HistoryResponse:
    return HistoryResponse(items=list_runs(limit=limit))


@app.get("/api/history/{run_id}")
def history_detail(run_id: str, _: None = Depends(require_extension_token)) -> Dict[str, Any]:
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    return run
