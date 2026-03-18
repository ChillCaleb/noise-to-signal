from __future__ import annotations

import csv
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from adapter_input import to_document
from main import build_document_from_text, build_document_from_url, run_llm, run_nlp

from .carbon_eval import CodeCarbonUnavailableError, summarize_compute, track_emissions
from .factcc_eval import FactCCAdapter, FactCCConfig, make_factcc_record, write_factcc_jsonl
from .metrics_schema import (
    EvaluationConfig,
    build_result,
    collect_csv_fields,
    flatten_result,
    make_article_id,
)
from .stability import score_stability
from .openai_eval import summarize_with_openai
from .summac_eval import SummaCConfig, SummaCEvaluator, SummaCUnavailableError


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def save_json(path: str, payload: Dict[str, Any]) -> str:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return path


def save_jsonl(path: str, rows: Iterable[Dict[str, Any]]) -> str:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def save_csv(path: str, rows: List[Dict[str, Any]]) -> str:
    ensure_dir(os.path.dirname(path))
    if not rows:
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write("")
        return path
    fieldnames = collect_csv_fields(rows)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def load_artifact(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data


def coerce_document_from_artifact(path: str) -> Dict[str, Any]:
    artifact = load_artifact(path)
    if artifact.get("schema") == "document:v1":
        return artifact
    if artifact.get("schema") == "analysis:v1":
        text = " ".join(section.get("text", "") for section in artifact.get("sections") or [])
        meta = artifact.get("meta") or {}
        return to_document(text=text, title=meta.get("title"), url=meta.get("url"))
    if "text" in artifact:
        return to_document(
            text=artifact["text"],
            title=artifact.get("title"),
            url=artifact.get("url"),
        )
    raise ValueError(f"Unsupported artifact format: {path}")


def resolve_document(*, input_text_or_url: Optional[str] = None, artifact_path: Optional[str] = None) -> Dict[str, Any]:
    if artifact_path:
        return coerce_document_from_artifact(artifact_path)
    if not input_text_or_url:
        raise ValueError("Either input_text_or_url or artifact_path is required.")
    raw = input_text_or_url.strip()
    return build_document_from_url(raw) if raw.startswith(("http://", "https://")) else build_document_from_text(raw)


def _evaluate_document(
    *,
    document: Dict[str, Any],
    config: EvaluationConfig,
    output_dir: str,
    artifact_path: Optional[str] = None,
    summary_text_override: Optional[str] = None,
) -> Dict[str, Any]:
    ensure_dir(output_dir)
    analysis = run_nlp(document)
    article_id = make_article_id(document["content"]["text"], (document.get("meta") or {}).get("url"))

    if summary_text_override is not None:
        generated_outputs = [summary_text_override]
        generation_compute = {
            "project_name": f"{config.run_id}-generation",
            "status": "skipped",
            "message": "Generation skipped because summary_text_override was provided.",
        }
    else:
        generated_outputs = []
        generation_compute = None
        for _ in range(max(config.stability_runs, 1)):
            generated = generate_summary_with_tracking(analysis, config)
            generated_outputs.append(generated["summary_text"])
            generation_compute = generated["compute"]

    summary_text = generated_outputs[0]
    metrics = score_summary(
        article_id=article_id,
        document=document,
        summary_text=summary_text,
        config=config,
    )
    metrics["stability"] = score_stability(generated_outputs)
    metrics["compute"] = summarize_compute(generation_compute, metrics.pop("compute_eval", None))

    if config.include_factcc:
        factcc_input_path = os.path.join(output_dir, f"{config.run_id}.factcc.jsonl")
        write_factcc_jsonl(
            [make_factcc_record(article_id, document["content"]["text"], summary_text)],
            factcc_input_path,
        )
        metrics["factcc"]["prepared_input_path"] = factcc_input_path

    result = build_result(
        article_id=article_id,
        source_url=(document.get("meta") or {}).get("url"),
        model_name=config.model_name,
        run_id=config.run_id,
        summary_text=summary_text,
        metrics=metrics,
        tier=config.tier,
        output_format=config.output_format,
        length=config.length,
        extra_meta={
            "artifact_source": artifact_path,
            "analysis_version": analysis.get("version"),
            "title": (document.get("meta") or {}).get("title"),
            "generation_skipped": summary_text_override is not None,
        },
    )
    result_dict = result.to_dict()
    save_json(os.path.join(output_dir, f"{config.run_id}.json"), result_dict)
    return result_dict


def generate_summary_with_tracking(analysis: Dict[str, Any], config: EvaluationConfig) -> Dict[str, Any]:
    carbon_dir = ensure_dir(os.path.join(config.carbon_output_dir, config.run_id))
    project_name = f"{config.run_id}-generation"
    if config.track_generation_carbon:
        try:
            with track_emissions(
                project_name,
                carbon_dir,
                country_iso_code=config.carbon_country_iso_code,
            ) as carbon_payload:
                text = _generate_summary(analysis, config)
            return {"summary_text": text, "compute": carbon_payload}
        except CodeCarbonUnavailableError as exc:
            text = _generate_summary(analysis, config)
            return {
                "summary_text": text,
                "compute": {
                    "project_name": project_name,
                    "status": "unavailable",
                    "message": str(exc),
                },
            }
    text = _generate_summary(analysis, config)
    return {"summary_text": text, "compute": None}


def _generate_summary(analysis: Dict[str, Any], config: EvaluationConfig) -> str:
    if config.provider == "openai":
        return summarize_with_openai(
            analysis,
            tier=config.tier,
            output_format=config.output_format,
            length=config.length,
            model=config.provider_model,
        )
    return run_llm(analysis, tier=config.tier, output_format=config.output_format, length=config.length)


def score_summary(
    *,
    article_id: str,
    document: Dict[str, Any],
    summary_text: str,
    config: EvaluationConfig,
) -> Dict[str, Any]:
    source_text = document["content"]["text"]
    summac = None
    if getattr(config, "enable_summac", True):
        summac = SummaCEvaluator(
            SummaCConfig(
                model_type=config.summac_model,
                device=config.summac_device,
            )
        )
    factcc_adapter = FactCCAdapter(
        FactCCConfig(
            mode=config.factcc_mode,
            checkpoint_path=config.factcc_checkpoint_path,
            eval_script=config.factcc_eval_script,
            python_bin=config.factcc_python_bin,
            hf_model=config.factcc_hf_model,
        )
    )
    carbon_dir = ensure_dir(os.path.join(config.carbon_output_dir, config.run_id))

    def _metric_block() -> Dict[str, Any]:
        if not getattr(config, "enable_summac", True):
            summac_metrics = {
                "status": "skipped",
                "message": "SummaC disabled for this run.",
                "score": None,
            }
        else:
            try:
                summac_metrics = summac.score(source_text, summary_text)
            except SummaCUnavailableError as exc:
                summac_metrics = {
                    "status": "unavailable",
                    "message": str(exc),
                    "score": None,
                }
        factcc_metrics = (
            factcc_adapter.score(article_id, source_text, summary_text)
            if config.include_factcc
            else {"status": "skipped", "score": None}
        )
        return {
            "summac": summac_metrics,
            "factcc": factcc_metrics,
        }

    if config.track_evaluation_carbon:
        try:
            with track_emissions(
                f"{config.run_id}-evaluation",
                carbon_dir,
                country_iso_code=config.carbon_country_iso_code,
            ) as carbon_payload:
                metric_block = _metric_block()
            compute = carbon_payload
        except CodeCarbonUnavailableError as exc:
            metric_block = _metric_block()
            compute = {
                "project_name": f"{config.run_id}-evaluation",
                "status": "unavailable",
                "message": str(exc),
            }
    else:
        metric_block = _metric_block()
        compute = None

    return {
        "summac": metric_block["summac"],
        "factcc": metric_block["factcc"],
        "compute_eval": compute,
    }


def evaluate_summary(
    *,
    input_text_or_url: Optional[str] = None,
    artifact_path: Optional[str] = None,
    config: Optional[EvaluationConfig] = None,
    output_dir: str = "artifacts/evaluation/single",
    summary_text_override: Optional[str] = None,
) -> Dict[str, Any]:
    cfg = config or EvaluationConfig()
    document = resolve_document(input_text_or_url=input_text_or_url, artifact_path=artifact_path)
    return _evaluate_document(
        document=document,
        config=cfg,
        output_dir=output_dir,
        artifact_path=artifact_path,
        summary_text_override=summary_text_override,
    )


def evaluate_document_summary(
    *,
    document: Dict[str, Any],
    config: Optional[EvaluationConfig] = None,
    output_dir: str = "artifacts/evaluation/single",
    summary_text_override: Optional[str] = None,
) -> Dict[str, Any]:
    cfg = config or EvaluationConfig()
    return _evaluate_document(
        document=document,
        config=cfg,
        output_dir=output_dir,
        summary_text_override=summary_text_override,
    )


def _iter_dataset_records(dataset_path: str) -> Iterable[Dict[str, Any]]:
    suffix = Path(dataset_path).suffix.lower()
    if suffix == ".jsonl":
        with open(dataset_path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    yield json.loads(line)
        return
    if suffix == ".json":
        payload = load_artifact(dataset_path)
        if isinstance(payload, list):
            for row in payload:
                yield row
            return
        raise ValueError("JSON dataset must contain a list of records.")
    if suffix == ".csv":
        with open(dataset_path, "r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                yield dict(row)
        return
    raise ValueError(f"Unsupported dataset format: {dataset_path}")


def _document_from_record(record: Dict[str, Any]) -> Dict[str, Any]:
    if record.get("schema") == "document:v1":
        return record
    text = record.get("text") or record.get("content", {}).get("text")
    if not text:
        raise ValueError("Dataset record must contain text or document:v1.")
    return to_document(text=text, title=record.get("title"), url=record.get("url"))


def run_batch_evaluation(
    *,
    dataset_path: Optional[str] = None,
    artifact_dir: Optional[str] = None,
    config: Optional[EvaluationConfig] = None,
    output_dir: str = "artifacts/evaluation/batch",
) -> Dict[str, str]:
    cfg = config or EvaluationConfig()
    ensure_dir(output_dir)

    if dataset_path:
        records = list(_iter_dataset_records(dataset_path))
        inputs = [
            {
                "document": _document_from_record(record),
                "summary_text": record.get("summary_text") or record.get("summary"),
            }
            for record in records
        ]
    elif artifact_dir:
        inputs = [
            {
                "document": coerce_document_from_artifact(str(path)),
                "summary_text": None,
            }
            for path in sorted(Path(artifact_dir).glob("*.json"))
        ]
    else:
        raise ValueError("dataset_path or artifact_dir is required for batch evaluation.")

    results: List[Dict[str, Any]] = []
    flat_rows: List[Dict[str, Any]] = []
    emission_paths = set()
    for index, item in enumerate(inputs):
        document = item["document"]
        run_cfg = EvaluationConfig(**{**asdict(cfg), "run_id": f"{cfg.run_id}-{index:04d}"})
        result = _evaluate_document(
            document=document,
            config=run_cfg,
            output_dir=output_dir,
            summary_text_override=item["summary_text"],
        )
        results.append(result)
        flat_rows.append(flatten_result(result))
        emission_paths.add(os.path.join(run_cfg.carbon_output_dir, run_cfg.run_id, "emissions.csv"))

    jsonl_path = save_jsonl(os.path.join(output_dir, "results.jsonl"), results)
    csv_path = save_csv(os.path.join(output_dir, "results.csv"), flat_rows)
    emissions_path = os.path.join(output_dir, "emissions_manifest.json")
    save_json(emissions_path, {"emissions_csv_paths": sorted(emission_paths)})
    return {
        "results_jsonl": jsonl_path,
        "results_csv": csv_path,
        "emissions_manifest": emissions_path,
    }
