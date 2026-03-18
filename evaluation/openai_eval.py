from __future__ import annotations

import os
from typing import Dict, Optional

from dotenv import load_dotenv
from groq import Groq

load_dotenv()


def get_default_openai_model() -> str:
    return "openai/gpt-oss-120b"


def summarize_with_openai(
    analysis: Dict,
    *,
    tier: str = "tier1",
    output_format: str = "text",
    length: str = "short",
    model: Optional[str] = None,
) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY missing in environment.")

    from llm_layer import _build_prompt, _validate_analysis

    _validate_analysis(analysis)
    prompt = _build_prompt(analysis, tier, output_format, length)
    system_msg = (
        "You are a precise news explainer. Return ONLY the final output. "
        "No JSON, no code fences."
        + (
            " Output must be valid HTML using h3,p,ul,li,strong,em only."
            if output_format == "html" else ""
        )
    )

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=model or get_default_openai_model(),
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=800,
    )
    return response.choices[0].message.content.strip()
