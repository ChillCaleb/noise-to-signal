import argparse
import sqlite3
import pandas as pd

def main(db_path: str = "database/noise2signal.db"):
    con = sqlite3.connect(db_path)
    # TODO: join events to prices, compute forward returns, write to `returns` table
    print("Backtest stub — fill in your logic here.")
    con.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="database/noise2signal.db")
    args = parser.parse_args()
    main(args.db)
