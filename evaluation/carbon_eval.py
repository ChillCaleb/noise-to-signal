from __future__ import annotations

import csv
import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Iterator, Optional


class CodeCarbonUnavailableError(RuntimeError):
    pass


@dataclass
class CarbonConfig:
    output_dir: str
    output_file: str = "emissions.csv"
    country_iso_code: str = "USA"
    offline: bool = True


def _load_tracker_class(offline: bool):
    try:
        from codecarbon import EmissionsTracker, OfflineEmissionsTracker
    except Exception as exc:
        raise CodeCarbonUnavailableError(
            "CodeCarbon is not installed. Install it from requirements-eval.txt."
        ) from exc
    return OfflineEmissionsTracker if offline else EmissionsTracker


def read_latest_emissions(csv_path: str) -> Dict[str, Any]:
    if not os.path.exists(csv_path):
        return {}
    with open(csv_path, "r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return rows[-1] if rows else {}


@contextmanager
def track_emissions(
    project_name: str,
    output_dir: str,
    *,
    output_file: str = "emissions.csv",
    country_iso_code: str = "USA",
    offline: bool = True,
    measure_power_secs: int = 1,
) -> Iterator[Dict[str, Any]]:
    os.makedirs(output_dir, exist_ok=True)
    tracker_cls = _load_tracker_class(offline)
    tracker = tracker_cls(
        project_name=project_name,
        output_dir=output_dir,
        output_file=output_file,
        save_to_file=True,
        country_iso_code=country_iso_code,
        measure_power_secs=measure_power_secs,
    )
    payload: Dict[str, Any] = {
        "project_name": project_name,
        "csv_path": os.path.join(output_dir, output_file),
        "started": True,
    }
    tracker.start()
    try:
        yield payload
    finally:
        emissions = tracker.stop()
        payload["emissions_kg"] = emissions
        payload["row"] = read_latest_emissions(payload["csv_path"])


def summarize_compute(*sections: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    total = 0.0
    for section in sections:
        if not section:
            continue
        key = section.get("project_name", "unknown")
        out[key] = section
        emissions = section.get("emissions_kg")
        if emissions is not None:
            total += float(emissions)
    out["total_emissions_kg"] = round(total, 12)
    return out
