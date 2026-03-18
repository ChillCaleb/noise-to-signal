from __future__ import annotations

import json
import os
from typing import Dict, List

import streamlit as st
from dotenv import load_dotenv

from app.ui.components import render_final_html
from evaluation import EvaluationConfig, evaluate_document_summary
from evaluation.openai_eval import get_default_openai_model, summarize_with_openai
from main import build_document_from_text, build_document_from_url
from main import run_llm, run_nlp

load_dotenv()


def _provider_status(provider: str) -> str:
    env_var = "GROQ_API_KEY"
    return "configured" if os.getenv(env_var) else f"missing {env_var}"


def _default_model(provider: str) -> str:
    if provider == "openai":
        return get_default_openai_model()
    return os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")


def _build_document(raw: str) -> Dict:
    raw = raw.strip()
    return build_document_from_url(raw) if raw.startswith(("http://", "https://")) else build_document_from_text(raw)


def _build_eval_config(
    *,
    tier: str,
    output_format: str,
    length: str,
    model_name: str,
    provider: str,
    provider_model: str,
    include_factcc: bool,
    enable_summac: bool,
    track_generation_carbon: bool,
    track_evaluation_carbon: bool,
    stability_runs: int,
    carbon_output_dir: str,
) -> EvaluationConfig:
    config = EvaluationConfig(
        tier=tier,
        output_format=output_format,
        length=length,
        model_name=model_name,
        provider=provider,
        provider_model=provider_model,
        include_factcc=include_factcc,
        enable_summac=enable_summac,
        track_generation_carbon=track_generation_carbon,
        track_evaluation_carbon=track_evaluation_carbon,
        stability_runs=stability_runs,
        carbon_output_dir=carbon_output_dir,
    )
    setattr(config, "factcc_checkpoint_path", os.getenv("FACTCC_CHECKPOINT_PATH"))
    setattr(config, "factcc_eval_script", os.getenv("FACTCC_EVAL_SCRIPT"))
    setattr(config, "factcc_python_bin", os.getenv("FACTCC_PYTHON_BIN", "python3"))
    setattr(config, "factcc_hf_model", os.getenv("FACTCC_HF_MODEL", "manueldeprada/FactCC"))
    setattr(config, "factcc_mode", os.getenv("FACTCC_MODE", "auto"))
    return config


def _render_metrics(result: Dict) -> None:
    metrics = result.get("metrics") or {}
    summac = metrics.get("summac") or {}
    stability = metrics.get("stability") or {}
    compute = metrics.get("compute") or {}
    factcc = metrics.get("factcc") or {}

    def _format_metric(value, digits: int = 6) -> str:
        if isinstance(value, (int, float)):
            return f"{value:.{digits}f}"
        return str(value) if value is not None else "n/a"

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Quality Metrics**")
        quality_rows = [
            ("SummaC", _format_metric(summac.get("score"), 6) if summac.get("score") is not None else summac.get("status", "n/a")),
            ("FactCC", _format_metric(factcc.get("score"), 6) if factcc.get("score") is not None else factcc.get("status", "n/a")),
            ("Exact Match", _format_metric(stability.get("exact_match_rate"), 4)),
            ("Seq Similarity", _format_metric(stability.get("mean_sequence_similarity"), 4)),
        ]
        for label, value in quality_rows:
            st.text(f"{label:<16} {value}")
    with col2:
        st.markdown("**Compute Metrics**")
        compute_rows = [
            ("Emissions (kg)", _format_metric(compute.get("total_emissions_kg"), 6)),
            ("Runs", _format_metric(stability.get("runs"), 0)),
            ("Unique Outputs", _format_metric(stability.get("unique_outputs"), 0)),
        ]
        for label, value in compute_rows:
            st.text(f"{label:<16} {value}")

    if summac.get("message"):
        st.caption(f"SummaC: {summac['message']}")
    if factcc.get("message"):
        st.caption(f"FactCC: {factcc['message']}")
    if compute.get("message"):
        st.caption(f"Compute: {compute['message']}")


def render_evaluation_view() -> None:
    st.title("Groq vs OpenAI")
    st.caption("Run the existing article pipeline once, then compare the original Groq summary against `openai/gpt-oss-120b` served through the Groq API.")

    raw_input = st.text_area(
        "Paste a URL or article text",
        placeholder="https://example.com/article or paste text here",
        height=180,
    )

    left, middle, right = st.columns(3)
    with left:
        tier = st.selectbox("Tier", ["tier1", "tier2"], index=0)
    with middle:
        output_format = st.selectbox("Format", ["text", "html"], index=0)
        length = st.selectbox("Length", ["short", "medium", "long"], index=0)
    with right:
        groq_model = st.text_input("Groq model", value=_default_model("groq"), disabled=True)
        openai_model = st.text_input("OpenAI model", value=_default_model("openai"), disabled=True)

    metric_left, metric_mid, metric_right = st.columns(3)
    with metric_left:
        run_summac = st.checkbox("Run SummaC", value=True)
        run_factcc = st.checkbox("Run FactCC if available", value=False)
    with metric_mid:
        run_codecarbon = st.checkbox("Track emissions", value=False)
        stability_runs = st.slider("Repeated runs", min_value=1, max_value=5, value=1)
    with metric_right:
        save_dir = st.text_input("Artifact output dir", value="artifacts/evaluation/ui")

    with st.expander("Provider setup", expanded=False):
        st.write(f"`groq`: {_provider_status('groq')} | default model: `{_default_model('groq')}`")
        st.write(f"`openai`: {_provider_status('openai')} | default model: `{_default_model('openai')}`")
        st.caption("`openai/gpt-oss-120b` is being called through the Groq API with your existing `GROQ_API_KEY`, matching the Groq playground model picker.")
        st.caption("FactCC will run via a local Salesforce checkpoint if `FACTCC_CHECKPOINT_PATH` and `FACTCC_EVAL_SCRIPT` are configured; otherwise it falls back to the Hugging Face model `manueldeprada/FactCC`.")

    if not st.button("Compare summaries", type="primary"):
        return

    if not raw_input.strip():
        st.warning("Provide a URL or article text.")
        return

    try:
        document = _build_document(raw_input)
    except Exception as exc:
        st.error(f"Input error: {exc}")
        return

    results: List[Dict] = []
    provider_configs = [
        ("Groq", _build_eval_config(
            tier=tier,
            output_format=output_format,
            length=length,
            model_name=f"Groq ({groq_model})",
            provider="groq",
            provider_model=groq_model,
            include_factcc=run_factcc,
            enable_summac=run_summac,
            track_generation_carbon=run_codecarbon,
            track_evaluation_carbon=run_codecarbon,
            stability_runs=stability_runs,
            carbon_output_dir=save_dir,
        )),
        ("OpenAI via Groq", _build_eval_config(
            tier=tier,
            output_format=output_format,
            length=length,
            model_name=f"OpenAI via Groq ({openai_model})",
            provider="openai",
            provider_model=openai_model,
            include_factcc=run_factcc,
            enable_summac=run_summac,
            track_generation_carbon=run_codecarbon,
            track_evaluation_carbon=run_codecarbon,
            stability_runs=stability_runs,
            carbon_output_dir=save_dir,
        )),
    ]

    for label, config in provider_configs:
        with st.spinner(f"Running {label}..."):
            try:
                result = evaluate_document_summary(
                    document=document,
                    config=config,
                    output_dir=save_dir,
                )
                results.append(result)
            except Exception as exc:
                st.error(f"{label} failed: {exc}")

    if not results:
        return

    cols = st.columns(len(results))
    for col, result in zip(cols, results):
        with col:
            st.subheader(result["model_name"])
            _render_metrics(result)
            if output_format == "html":
                render_final_html(result["summary_text"], height=420, scrolling=True)
            else:
                st.text_area(
                    result["model_name"],
                    value=result["summary_text"],
                    height=260,
                    key=f"summary-{result['run_id']}",
                )
            with st.expander("Raw metrics"):
                st.code(json.dumps(result.get("metrics") or {}, ensure_ascii=False, indent=2), language="json")
