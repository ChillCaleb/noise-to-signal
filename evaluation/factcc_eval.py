from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class FactCCConfig:
    mode: str = "auto"
    checkpoint_path: Optional[str] = None
    eval_script: Optional[str] = None
    python_bin: str = "python3"
    hf_model: str = "manueldeprada/FactCC"


def _env_or(value: Optional[str], env_name: str) -> Optional[str]:
    return value or os.getenv(env_name)


def discover_factcc_config(config: Optional[FactCCConfig] = None) -> FactCCConfig:
    cfg = config or FactCCConfig()
    checkpoint_path = _env_or(cfg.checkpoint_path, "FACTCC_CHECKPOINT_PATH")
    eval_script = _env_or(cfg.eval_script, "FACTCC_EVAL_SCRIPT")
    python_bin = _env_or(cfg.python_bin, "FACTCC_PYTHON_BIN") or "python3"
    mode = _env_or(cfg.mode, "FACTCC_MODE") or "auto"
    hf_model = _env_or(cfg.hf_model, "FACTCC_HF_MODEL") or "manueldeprada/FactCC"

    if mode == "auto":
        if checkpoint_path and eval_script and os.path.exists(checkpoint_path) and os.path.exists(eval_script):
            mode = "subprocess"
        else:
            mode = "hf"

    return FactCCConfig(
        mode=mode,
        checkpoint_path=checkpoint_path,
        eval_script=eval_script,
        python_bin=python_bin,
        hf_model=hf_model,
    )


def make_factcc_record(article_id: str, source_text: str, claim_text: str) -> Dict[str, str]:
    return {
        "id": article_id,
        "text": source_text,
        "claim": claim_text,
    }


def write_factcc_jsonl(records: List[Dict[str, str]], output_path: str) -> str:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return output_path


class FactCCAdapter:
    def __init__(self, config: Optional[FactCCConfig] = None):
        self.config = discover_factcc_config(config)

    def score(self, article_id: str, source_text: str, summary_text: str) -> Dict[str, Any]:
        if self.config.mode == "subprocess":
            return self._score_with_subprocess(article_id, source_text, summary_text)
        if self.config.mode == "hf":
            return self._score_with_huggingface(article_id, source_text, summary_text)
        return self._placeholder_result(article_id, source_text, summary_text)

    def _placeholder_result(self, article_id: str, source_text: str, summary_text: str) -> Dict[str, Any]:
        return {
            "status": "not_run",
            "mode": self.config.mode,
            "message": (
                "FactCC inference is not wired by default. Use the prepared JSONL artifact "
                "with a local salesforce/factCC checkpoint workflow or replace this adapter."
            ),
            "prepared_input": make_factcc_record(article_id, source_text, summary_text),
            "score": None,
            "checkpoint_path": self.config.checkpoint_path,
            "eval_script": self.config.eval_script,
            "hf_model": self.config.hf_model,
        }

    def _score_with_subprocess(self, article_id: str, source_text: str, summary_text: str) -> Dict[str, Any]:
        if not self.config.eval_script:
            raise ValueError("FactCC subprocess mode requires eval_script.")
        if not self.config.checkpoint_path:
            raise ValueError("FactCC subprocess mode requires checkpoint_path.")

        work_dir = os.path.dirname(self.config.eval_script) or "."
        input_path = os.path.join(work_dir, "data-dev.jsonl")
        output_path = os.path.join(work_dir, "factcc_predictions.json")
        write_factcc_jsonl([make_factcc_record(article_id, source_text, summary_text)], input_path)

        command = [
            self.config.python_bin,
            self.config.eval_script,
            "--checkpoint_path",
            self.config.checkpoint_path,
            "--data_path",
            input_path,
            "--output_path",
            output_path,
        ]
        completed = subprocess.run(
            command,
            cwd=work_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        result: Dict[str, Any] = {
            "status": "ok" if completed.returncode == 0 else "error",
            "mode": "subprocess",
            "command": command,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
            "prepared_input_path": input_path,
            "output_path": output_path,
            "score": None,
        }
        if completed.returncode == 0 and os.path.exists(output_path):
            try:
                with open(output_path, "r", encoding="utf-8") as handle:
                    result["raw"] = json.load(handle)
                result["score"] = _extract_factcc_score(result["raw"])
            except Exception as exc:
                result["parse_error"] = str(exc)
        return result

    def _score_with_huggingface(self, article_id: str, source_text: str, summary_text: str) -> Dict[str, Any]:
        try:
            import torch
            from transformers import BertForSequenceClassification, BertTokenizer
        except Exception as exc:
            return {
                "status": "error",
                "mode": "hf",
                "message": f"Hugging Face FactCC inference dependencies are missing: {exc}",
                "score": None,
                "prepared_input": make_factcc_record(article_id, source_text, summary_text),
                "hf_model": self.config.hf_model,
            }

        try:
            tokenizer = BertTokenizer.from_pretrained(self.config.hf_model)
            model = BertForSequenceClassification.from_pretrained(self.config.hf_model)
            inputs = tokenizer(
                source_text,
                summary_text,
                max_length=512,
                padding="max_length",
                truncation="only_first",
                return_tensors="pt",
            )
            with torch.no_grad():
                logits = model(**inputs).logits
            probs = torch.softmax(logits, dim=1).cpu().tolist()[0]
            pred = logits.argmax(dim=1).item()
            label = model.config.id2label[pred]
            score = probs[pred]
        except Exception as exc:
            return {
                "status": "error",
                "mode": "hf",
                "message": f"Hugging Face FactCC inference failed: {exc}",
                "score": None,
                "prepared_input": make_factcc_record(article_id, source_text, summary_text),
                "hf_model": self.config.hf_model,
            }

        return {
            "status": "ok",
            "mode": "hf",
            "score": float(score),
            "label": label,
            "raw": {
                "probabilities": probs,
                "predicted_index": pred,
            },
            "prepared_input": make_factcc_record(article_id, source_text, summary_text),
            "hf_model": self.config.hf_model,
        }


def _extract_factcc_score(payload: Any) -> Optional[float]:
    if isinstance(payload, dict):
        for key in ["score", "factcc_score", "pred_prob", "probability"]:
            value = payload.get(key)
            if isinstance(value, (int, float)):
                return float(value)
        for key in ["predictions", "results", "data"]:
            value = payload.get(key)
            score = _extract_factcc_score(value)
            if score is not None:
                return score
        return None
    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, dict):
            label = first.get("label") or first.get("prediction")
            if isinstance(label, str):
                low = label.lower()
                if low in {"supported", "entailment", "correct", "true"}:
                    return 1.0
                if low in {"unsupported", "contradiction", "incorrect", "false"}:
                    return 0.0
        return _extract_factcc_score(first)
    return None
