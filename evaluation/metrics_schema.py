from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def make_run_id(prefix: str = "eval") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def make_article_id(source_text: str, source_url: Optional[str] = None) -> str:
    base = source_url or source_text
    return "article-" + hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


@dataclass
class EvaluationConfig:
    tier: str = "tier1"
    output_format: str = "text"
    length: str = "short"
    model_name: str = "groq"
    provider: str = "groq"
    provider_model: Optional[str] = None
    run_id: str = field(default_factory=make_run_id)
    include_factcc: bool = False
    factcc_checkpoint_path: Optional[str] = None
    factcc_eval_script: Optional[str] = None
    factcc_python_bin: str = "python3"
    factcc_hf_model: str = "manueldeprada/FactCC"
    enable_summac: bool = True
    summac_model: str = "conv"
    summac_device: Optional[str] = None
    factcc_mode: str = "placeholder"
    track_generation_carbon: bool = True
    track_evaluation_carbon: bool = True
    stability_runs: int = 1
    carbon_output_dir: str = "artifacts/evaluation"
    carbon_country_iso_code: str = "USA"


@dataclass
class EvaluationMeta:
    timestamp: str
    tier: str
    output_format: str
    length: str


@dataclass
class EvaluationResult:
    article_id: str
    source_url: Optional[str]
    model_name: str
    run_id: str
    summary_text: str
    metrics: Dict[str, Any]
    meta: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def build_result(
    *,
    article_id: str,
    source_url: Optional[str],
    model_name: str,
    run_id: str,
    summary_text: str,
    metrics: Dict[str, Any],
    tier: str,
    output_format: str,
    length: str,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> EvaluationResult:
    meta = EvaluationMeta(
        timestamp=now_iso(),
        tier=tier,
        output_format=output_format,
        length=length,
    )
    meta_dict = asdict(meta)
    if extra_meta:
        meta_dict.update(extra_meta)
    return EvaluationResult(
        article_id=article_id,
        source_url=source_url,
        model_name=model_name,
        run_id=run_id,
        summary_text=summary_text,
        metrics=metrics,
        meta=meta_dict,
    )


def flatten_result(result: Dict[str, Any]) -> Dict[str, Any]:
    flat: Dict[str, Any] = {
        "article_id": result.get("article_id"),
        "source_url": result.get("source_url"),
        "model_name": result.get("model_name"),
        "run_id": result.get("run_id"),
        "summary_text": result.get("summary_text"),
    }

    def _walk(prefix: str, value: Any) -> None:
        if isinstance(value, dict):
            for key, subvalue in value.items():
                next_prefix = f"{prefix}.{key}" if prefix else key
                _walk(next_prefix, subvalue)
            return
        if isinstance(value, list):
            flat[prefix] = json.dumps(value, ensure_ascii=False)
            return
        flat[prefix] = value

    _walk("metrics", result.get("metrics") or {})
    _walk("meta", result.get("meta") or {})
    return flat


def collect_csv_fields(rows: List[Dict[str, Any]]) -> List[str]:
    ordered: List[str] = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                ordered.append(key)
    return ordered
