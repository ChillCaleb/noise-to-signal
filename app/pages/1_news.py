import os
from datetime import date, timedelta
import requests
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY")

st.set_page_config(page_title="News Feed", layout="wide")
st.title("📰 News Feed")

# Controls (broad feed by default; no article page, just a list)
col1, col2, col3 = st.columns([2,1,1])
with col1:
    query = st.text_input("Keyword (leave blank for broad feed)", value="")
with col2:
    days_back = st.number_input("Days back", 1, 30, 7)
with col3:
    limit = st.slider("Rows per source", 5, 100, 20, 5)

start = (date.today() - timedelta(days=days_back)).isoformat()
end   = date.today().isoformat()

def norm_dt(series):
    """Return tz-aware UTC datetimes (works for mixed tz/naive)."""
    # utc=True will localize naive to UTC and keep aware as UTC
    return pd.to_datetime(series, utc=True, errors="coerce")

@st.cache_data(ttl=300)
def fetch_newsapi(q: str, start: str, end: str, limit: int):
    if not NEWSAPI_KEY:
        return pd.DataFrame(), "Missing NEWSAPI_KEY"
    # If no query provided, use top-headlines (broad business feed)
    if not q.strip():
        url = "https://newsapi.org/v2/top-headlines"
        params = {
            "category": "business",
            "language": "en",
            "pageSize": min(limit, 100),
            "apiKey": NEWSAPI_KEY
        }
    else:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": q,
            "from": start,
            "to": end,
            "sortBy": "publishedAt",
            "language": "en",
            "pageSize": min(limit, 100),
            "apiKey": NEWSAPI_KEY
        }
    r = requests.get(url, params=params, timeout=20)
    data = r.json() if r.headers.get("content-type","").startswith("application/json") else {}
    if data.get("status") != "ok":
        return pd.DataFrame(), data.get("message", "NewsAPI error")
    rows = [{
        "source": a["source"]["name"],
        "title": a.get("title"),
        "description": a.get("description"),
        "datetime": a.get("publishedAt"),
        "url": a.get("url")
    } for a in data.get("articles", [])]
    df = pd.DataFrame(rows)
    if not df.empty:
        df["datetime"] = norm_dt(df["datetime"])
    return df, None

@st.cache_data(ttl=300)
def fetch_finnhub(q_or_symbol: str, start: str, end: str, limit: int):
    if not FINNHUB_KEY:
        return pd.DataFrame(), "Missing FINNHUB_API_KEY"
    base = "https://finnhub.io/api/v1"
    params = {"token": FINNHUB_KEY}
    rows = []

    # 1) Try company news if they typed a ticker
    if q_or_symbol.strip():
        r = requests.get(f"{base}/company-news",
                         params={**params, "symbol": q_or_symbol, "from": start, "to": end},
                         timeout=20)
        if r.status_code == 200:
            for n in r.json()[:limit]:
                rows.append({
                    "source": n.get("source"),
                    "title": n.get("headline"),
                    "description": n.get("summary"),
                    "datetime": pd.to_datetime(n.get("datetime"), unit="s", utc=True),
                    "url": n.get("url")
                })

    # 2) Fallback to general news if none returned
    if not rows:
        g = requests.get(f"{base}/news",
                         params={**params, "category": "general", "minId": 0},
                         timeout=20)
        if g.status_code == 200:
            for x in g.json()[:limit]:
                rows.append({
                    "source": x.get("source"),
                    "title": x.get("headline"),
                    "description": x.get("summary"),
                    "datetime": pd.to_datetime(x.get("datetime"), unit="s", utc=True),
                    "url": x.get("url")
                })

    df = pd.DataFrame(rows)
    return df, None

# Fetch
newsapi_df, e1 = fetch_newsapi(query, start, end, limit)
finnhub_df, e2 = fetch_finnhub(query, start, end, limit)

if e1 or e2:
    st.warning(" • ".join([e for e in [e1, e2] if e]))

# Present exactly like the notebook: a simple combined table, no links
combined = pd.concat([newsapi_df, finnhub_df], ignore_index=True)
if combined.empty:
    st.info("No results.")
else:
    combined["datetime"] = norm_dt(combined["datetime"])  # tz-aware UTC
    combined = combined.sort_values("datetime", ascending=False).reset_index(drop=True)
    # Reorder to match the ipynb style: source | title | description | datetime | url
    show = combined[["source", "title", "description", "datetime", "url"]]
    st.dataframe(show, use_container_width=True, hide_index=True)
