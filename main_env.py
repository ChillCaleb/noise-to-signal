import os
import sys
import subprocess
import sqlite3
import argparse
import time
from pathlib import Path

# ════════════════════════════════════════════════
# GLOBALS
# ════════════════════════════════════════════════
PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "database" / "noise2signal.db"

# ════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════
def status(msg, icon="⚙️"):
    print(f"{icon}  {msg}")

def success(msg):
    print(f"✅  {msg}")

def warn(msg):
    print(f"⚠️  {msg}")

def error(msg):
    print(f"❌  {msg}")
    sys.exit(1)

def run(cmd, check=True):
    """Run a subprocess in the current environment."""
    print(f"→ {' '.join(map(str, cmd))}")
    return subprocess.run(cmd, cwd=PROJECT_ROOT, check=check)

# ════════════════════════════════════════════════
# ENVIRONMENT INSPECTION
# ════════════════════════════════════════════════
def show_active_env():
    """Show which Python and packages are active."""
    venv_path = os.environ.get("VIRTUAL_ENV")
    if not venv_path:
        warn("No active virtual environment detected! You're running in system Python.")
        return
    success(f"Active virtual environment: {venv_path}")
    py = sys.executable
    status(f"Python executable: {py}")
    run([py, "-c", "import sys; print('Python', sys.version)"])
    run([py, "-m", "pip", "list"])

# ════════════════════════════════════════════════
# DATABASE
# ════════════════════════════════════════════════
def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    status(f"Preparing SQLite database at {DB_PATH}...")
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS events(
        event_id TEXT PRIMARY KEY,
        timestamp_utc TEXT NOT NULL,
        source TEXT,
        headline TEXT NOT NULL,
        url TEXT,
        themes TEXT
    );""")
    success("Table 'events' ready."); time.sleep(0.15)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS event_entities(
        event_id TEXT NOT NULL,
        ticker TEXT NOT NULL,
        role TEXT,
        PRIMARY KEY(event_id, ticker),
        FOREIGN KEY(event_id) REFERENCES events(event_id)
    );""")
    success("Table 'event_entities' ready."); time.sleep(0.15)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS prices(
        ticker TEXT NOT NULL,
        date TEXT NOT NULL,
        open REAL, high REAL, low REAL, close REAL, adj_close REAL, volume INTEGER,
        PRIMARY KEY(ticker, date)
    );""")
    success("Table 'prices' ready."); time.sleep(0.15)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS returns(
        event_id TEXT NOT NULL,
        ticker TEXT NOT NULL,
        horizon INTEGER NOT NULL,
        fwd_ret REAL,
        PRIMARY KEY(event_id, ticker, horizon),
        FOREIGN KEY(event_id) REFERENCES events(event_id)
    );""")
    success("Table 'returns' ready.")

    con.commit(); con.close()
    success("Database initialized.")

# ════════════════════════════════════════════════
# BACKTEST STUB
# ════════════════════════════════════════════════
def run_backtest_stub():
    import pandas as pd
    if not DB_PATH.exists():
        warn("Database not found; creating one now...")
        init_db()

    con = sqlite3.connect(DB_PATH)
    try:
        n = pd.read_sql_query("SELECT COUNT(*) AS n FROM events", con).iloc[0]["n"]
        success(f"Backtest stub: events in DB = {n}")
    except Exception as e:
        warn(f"Could not read events table: {e}")
    con.close()

# ════════════════════════════════════════════════
# STREAMLIT APP
# ════════════════════════════════════════════════
def run_streamlit():
    app_entry = PROJECT_ROOT / "app" / "Home.py"
    if not app_entry.exists():
        error("Streamlit entry not found at app/Home.py")
    status("Launching Streamlit (Ctrl+C to stop)...")
    py = sys.executable
    run([py, "-m", "streamlit", "run", str(app_entry)], check=False)

# ════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="Noise→Signal (in-env) Runner")
    parser.add_argument(
        "cmd",
        nargs="?",
        default="info",
        choices=["info", "init-db", "backtest", "app", "all"],
        help="Command to run inside active environment.",
    )
    args = parser.parse_args()

    print("==============================================")
    print("💻 Noise → Signal In-Environment Runner")
    print("==============================================")

    if args.cmd in ("info", "all"):
        show_active_env(); print("")

    if args.cmd in ("init-db", "all"):
        init_db(); print("")

    if args.cmd in ("backtest", "all"):
        run_backtest_stub(); print("")

    if args.cmd in ("app", "all"):
        run_streamlit()

    success("All requested tasks finished.\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        warn("Process interrupted by user.")
