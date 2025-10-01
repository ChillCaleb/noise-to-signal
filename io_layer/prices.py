import yfinance as yf
import pandas as pd

def get_prices(ticker: str, start="2020-01-01", end=None) -> pd.DataFrame:
    df = yf.download(ticker, start=start, end=end, progress=False)
    if df.empty:
        raise ValueError(f"No data for {ticker}")
    return df[["Open","High","Low","Close","Volume"]].rename_axis("Date").reset_index()
