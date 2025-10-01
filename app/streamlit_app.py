# ensure imports work when Streamlit runs from app/ directory
import os, sys
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import streamlit as st
import json, datetime as dt
from nlp.sentiment import sentiment_scores, label_from_compound
from nlp.ner_linking import link_text_to_tickers
import json
import datetime as dt

# app/streamlit_app.py
from io_layer.db import init_db, insert_raw, insert_event
# anywhere else:
# from io_layer.prices import get_prices

init_db()
st.title("Noise → Signal (Day 1)")
text = st.text_area("Paste a headline / post")

if st.button("Parse"):
    tickers = link_text_to_tickers(text)
    s = sentiment_scores(text)
    label = label_from_compound(s["compound"])
    ts = dt.datetime.utcnow().isoformat(timespec="seconds")
    rid = insert_raw(ts, "manual", text)
    eid = insert_event(rid, json.dumps(tickers), s["compound"], label, "day1:vader+spacy_small")
    st.json({"tickers": tickers, "sentiment": s, "label": label, "raw_id": rid, "event_id": eid})
