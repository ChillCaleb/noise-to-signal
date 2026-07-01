from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_DB_PATH = Path("data/noise_to_signal_extension.db")


def get_db_path() -> Path:
    configured = os.getenv("NOISE_SIGNAL_DB")
    return Path(configured) if configured else DEFAULT_DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS analysis_runs (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  title TEXT,
  url TEXT,
  input_text TEXT,
  document_json TEXT NOT NULL,
  analysis_json TEXT NOT NULL,
  summary_text TEXT NOT NULL,
  tier TEXT NOT NULL,
  output_format TEXT NOT NULL,
  length TEXT NOT NULL,
  model TEXT,
  source_type TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_analysis_runs_created_at
ON analysis_runs(created_at DESC);
"""


def connect() -> sqlite3.Connection:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def save_run(
    *,
    run_id: str,
    created_at: str,
    title: Optional[str],
    url: Optional[str],
    input_text: str,
    document: Dict[str, Any],
    analysis: Dict[str, Any],
    summary_text: str,
    tier: str,
    output_format: str,
    length: str,
    model: Optional[str],
    source_type: str,
) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO analysis_runs (
              id, created_at, title, url, input_text, document_json,
              analysis_json, summary_text, tier, output_format, length,
              model, source_type
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                created_at,
                title,
                url,
                input_text,
                json.dumps(document, ensure_ascii=False),
                json.dumps(analysis, ensure_ascii=False),
                summary_text,
                tier,
                output_format,
                length,
                model,
                source_type,
            ),
        )
        conn.commit()


def list_runs(limit: int = 25) -> List[Dict[str, Any]]:
    init_db()
    bounded_limit = max(1, min(limit, 100))
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, created_at, title, url, summary_text, tier, output_format, length
            FROM analysis_runs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (bounded_limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    init_db()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM analysis_runs
            WHERE id = ?
            """,
            (run_id,),
        ).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["document"] = json.loads(data.pop("document_json"))
    data["analysis"] = json.loads(data.pop("analysis_json"))
    return data

