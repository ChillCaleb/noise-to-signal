import sqlite3
from pathlib import Path

DB_PATH = Path("data/tradeideas.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_text(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  source TEXT,
  text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  raw_id INTEGER NOT NULL,
  tickers TEXT NOT NULL,         -- JSON string of tickers
  sentiment REAL NOT NULL,       -- VADER compound
  label TEXT NOT NULL,           -- bucketed label
  model_version TEXT NOT NULL,
  FOREIGN KEY(raw_id) REFERENCES raw_text(id)
);
"""

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        for stmt in SCHEMA.strip().split(";"):
            if stmt.strip():
                cur.execute(stmt)
        conn.commit()

def insert_raw(ts: str, source: str, text: str) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO raw_text(ts,source,text) VALUES (?,?,?)", (ts, source, text))
        conn.commit()
        return cur.lastrowid

def insert_event(raw_id: int, tickers_json: str, sentiment: float, label: str, model_version: str) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("""INSERT INTO events(raw_id,tickers,sentiment,label,model_version)
                       VALUES (?,?,?,?,?)""",
                    (raw_id, tickers_json, sentiment, label, model_version))
        conn.commit()
        return cur.lastrowid
