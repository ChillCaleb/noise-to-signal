# llm_layer.py
# analysis:v1 (from nlp_layer) -> final text or HTML via Groq

from typing import Dict
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()  # read .env once on import

# ---------- Public API ----------

def summarize(
    analysis: Dict,
    tier: str = "tier1",            # "tier1" | "tier2"
    output_format: str = "text",    # "text" | "html"
    length: str = "short"           # "short" | "medium" | "long"
) -> str:
    _validate_analysis(analysis)
    prompt = _build_prompt(analysis, tier, output_format, length)
    return _run_llm(prompt, output_format)


# ---------- Internal: prompt ----------

def _build_prompt(analysis: Dict, tier: str, output_format: str, length: str) -> str:
    meta = analysis.get("meta") or {}
    stats = analysis.get("stats") or {}
    sections = analysis.get("sections") or []

    title = meta.get("title") or "Untitled"
    url = meta.get("url") or ""
    stance = (analysis.get("modality") or {}).get("stance_index")
    keywords = ", ".join((analysis.get("keywords") or [])[:10])

    # pack a compact context body
    body = " ".join(s.get("text", "") for s in sections)[:4000]

    len_map = {"short": "≈120 words", "medium": "≈220 words", "long": "≈350 words"}
    length_hint = len_map.get(length, "≈150 words")

    output_instr = (
        "Return ONLY valid HTML using <h3>, <p>, <ul>, <li>, <strong>, <em>. "
        "No code fences, scripts, styles, or inline event handlers."
        if output_format == "html"
        else "Return ONLY plain text. No JSON. No code fences."
    )

    tier_instr = (
        "Tier 1: Faithful recap of what happened and the core result. Avoid speculation."
        if tier == "tier1"
        else "Tier 2: Briefly explain why it matters and the immediate implications. Stay grounded."
    )

    header = (
        f"TITLE: {title}\n"
        f"SOURCE: {url}\n"
        f"WORDS: {stats.get('words')} | STANCE_INDEX: {stance}\n"
        f"KEYWORDS: {keywords}\n"
    )

    instructions = (
        "You are a precise finance/policy news explainer.\n"
        f"{tier_instr}\n"
        f"Write {length_hint}. {output_instr}\n"
        "Be specific and neutral. If uncertain, say so."
    )

    return f"{instructions}\n\nCONTEXT:\n{header}\n\nTEXT:\n{body}\n"


# ---------- Internal: Groq call ----------

def _run_llm(prompt: str, output_format: str) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY missing in environment.")

    # Choose a current, supported model (override via GROQ_MODEL if you want)
    model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

    client = Groq(api_key=api_key)
    system_msg = (
        "You are a precise news explainer. Return ONLY the final output. "
        "No JSON, no code fences."
        + (
            " Output must be valid HTML using h3,p,ul,li,strong,em only."
            if output_format == "html" else ""
        )
    )

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=800,
    )
    return resp.choices[0].message.content.strip()


# ---------- Internal: minimal validation ----------

def _validate_analysis(analysis: Dict) -> None:
    if not isinstance(analysis, dict):
        raise TypeError("analysis must be a dict")
    if analysis.get("schema") != "analysis:v1":
        raise ValueError("analysis.schema must be 'analysis:v1'")
    secs = analysis.get("sections")
    if not secs or not isinstance(secs, list):
        raise ValueError("analysis.sections is required")
