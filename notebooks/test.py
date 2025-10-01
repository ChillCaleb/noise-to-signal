import json, datetime as dt
from nlp.sentiment import sentiment_scores, label_from_compound
from nlp.ner_linking import link_text_to_tickers
from io_layer.db import init_db, insert_raw, insert_event

init_db()

headline = "Pentagon awards $2B missile defense contract to Lockheed Martin; RTX to supply components."
ts = dt.datetime.utcnow().isoformat(timespec="seconds")

tickers = link_text_to_tickers(headline)            # expects ['LMT','RTX'] if spaCy is available
sent = sentiment_scores(headline)["compound"]
label = label_from_compound(sent)

raw_id = insert_raw(ts, "manual", headline)
event_id = insert_event(raw_id, json.dumps(tickers), sent, label, "day1:vader+spacy_small")

print({"raw_id": raw_id, "event_id": event_id, "tickers": tickers, "sentiment": sent, "label": label})
