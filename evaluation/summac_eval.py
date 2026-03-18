from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests


class SummaCUnavailableError(RuntimeError):
    pass


@dataclass
class SummaCConfig:
    model_type: str = "conv"
    model_name: str = "vitc"
    granularity: str = "sentence"
    bins: str = "percentile"
    nli_labels: str = "e"
    agg: str = "mean"
    device: Optional[str] = None
    start_file: str = "default"
    cache_dir: str = os.path.expanduser("~/.cache/noise-to-signal/summac")


def _resolve_device(device: Optional[str]) -> str:
    if device:
        return device
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


class SummaCEvaluator:
    def __init__(self, config: Optional[SummaCConfig] = None):
        self.config = config or SummaCConfig()
        self.device = _resolve_device(self.config.device)
        self._model = None

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        self._ensure_nltk_resources()
        try:
            from summac.model_summac import SummaCConv, SummaCZS
        except Exception as exc:
            raise SummaCUnavailableError(
                "SummaC is not installed or failed to import. Install torch first, then summac."
            ) from exc

        start_file = self._resolve_start_file()
        if self.config.model_type == "zs":
            self._model = SummaCZS(
                granularity=self.config.granularity,
                model_name=self.config.model_name,
                device=self.device,
            )
        else:
            self._model = SummaCConv(
                models=[self.config.model_name],
                bins=self.config.bins,
                granularity=self.config.granularity,
                nli_labels=self.config.nli_labels,
                device=self.device,
                start_file=start_file,
                agg=self.config.agg,
            )
        return self._model

    def _resolve_start_file(self) -> Optional[str]:
        if self.config.model_type == "zs":
            return None
        if self.config.start_file not in (None, "default"):
            return self.config.start_file
        os.makedirs(self.config.cache_dir, exist_ok=True)
        checkpoint_name = "summac_conv_vitc_sent_perc_e.bin"
        checkpoint_path = os.path.join(self.config.cache_dir, checkpoint_name)
        if os.path.exists(checkpoint_path):
            return checkpoint_path

        url = f"https://github.com/tingofurro/summac/raw/master/{checkpoint_name}"
        try:
            response = requests.get(url, timeout=120)
            response.raise_for_status()
        except Exception as exc:
            raise SummaCUnavailableError(
                f"Failed to download SummaC checkpoint from {url}: {exc}"
            ) from exc

        with open(checkpoint_path, "wb") as handle:
            handle.write(response.content)
        return checkpoint_path

    def _ensure_nltk_resources(self) -> None:
        try:
            import nltk
        except Exception as exc:
            raise SummaCUnavailableError(
                "NLTK is not installed. Install evaluation dependencies to run SummaC."
            ) from exc
        for resource_name, resource_path in [
            ("punkt", "tokenizers/punkt"),
            ("punkt_tab", "tokenizers/punkt_tab/english"),
        ]:
            try:
                nltk.data.find(resource_path)
            except LookupError:
                try:
                    nltk.download(resource_name, quiet=True)
                except Exception as exc:
                    raise SummaCUnavailableError(
                        f"Failed to download required NLTK resource '{resource_name}': {exc}"
                    ) from exc

    def score(self, document_text: str, summary_text: str) -> Dict[str, Any]:
        model = self._load_model()
        raw = model.score([document_text], [summary_text])
        scores = raw.get("scores") or []
        score = scores[0] if scores else None
        return {
            "model": f"SummaC{self.config.model_type.capitalize()}",
            "variant": self.config.model_name,
            "granularity": self.config.granularity,
            "device": self.device,
            "score": score,
            "raw": raw,
        }
