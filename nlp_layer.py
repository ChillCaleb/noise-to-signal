# nlp_layer.py
# Input schema:  document:v1  (from adapter_input.py)
# Output schema: analysis:v1  (for llm_layer consumption)
#
# Zero network calls. Pure text processing.

import json, sys, time, hashlib, regex, re
from typing import Dict, Any, List, Optional
from dateutil import parser as dparser

ANALYSIS_VERSION = "nlp-layer:1.0.0"

# ------------------------- Validation ----------------------------------------
def _require(cond: bool, msg: str):
    if not cond:
        raise ValueError(msg)

def validate_document(doc: Dict[str, Any]) -> None:
    _require(isinstance(doc, dict), "document must be a dict")
    _require(doc.get("schema") == "document:v1", "schema must be 'document:v1'")
    _require("content" in doc and isinstance(doc["content"], dict), "missing content")
    text = doc["content"].get("text")
    _require(isinstance(text, str) and text.strip(), "content.text must be non-empty string")

# ------------------------- Helpers -------------------------------------------
def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def _sha256(s: str) -> str:
    return "sha256:" + hashlib.sha256(s.encode("utf-8")).hexdigest()

def _normalize_text(text: str) -> str:
    # Normalize quotes/dashes, collapse whitespace but keep paragraph breaks
    trans = str.maketrans({'\u2018':"'", '\u2019':"'", '\u201C':'"', '\u201D':'"', '\u2013':'-', '\u2014':'-'})
    text = text.translate(trans)
    # strip trailing spaces per line and remove duplicate blank lines
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]  # drop empty lines
    text = "\n".join(lines)
    # compact internal whitespace
    text = regex.sub(r'\s+', ' ', text)
    return text.strip()

def _split_sections(text: str, max_words: int = 180) -> List[Dict[str, Any]]:
    # simple word-budget chunker to keep sections readable
    paras = [p.strip() for p in text.split('\n') if p.strip()]
    chunks, buf, wc = [], [], 0
    for p in paras:
        w = len(p.split())
        if wc + w > max_words and buf:
            chunk = " ".join(buf)
            chunks.append({"heading": None, "text": chunk, "word_count": len(chunk.split())})
            buf, wc = [], 0
        buf.append(p); wc += w
    if buf:
        chunk = " ".join(buf)
        chunks.append({"heading": None, "text": chunk, "word_count": len(chunk.split())})
    return chunks if chunks else [{"heading": None, "text": text, "word_count": len(text.split())}]

# ------------------------- Extractors ----------------------------------------
RE_MONEY   = regex.compile(r'(?:(?:USD|US\$|\$)\s?\d[\d,]*(?:\.\d{1,2})?)', regex.I)
RE_PERCENT = regex.compile(r'\b\d{1,3}(?:\.\d+)?\s?%|\b\d(?:[/\-]\d)?\s?percent', regex.I)
RE_NUMBER  = regex.compile(r'\b\d{1,4}(?:,\d{3})*(?:\.\d+)?\b')
RE_TICKER  = regex.compile(r'\b[A-Z]{1,5}\b')
RE_QUOTE   = regex.compile(r'\"([^"]{10,400})\"|\“([^”]{10,400})\”')

HEDGE = {"may","might","could","suggest","appears","possible","likely","unlikely","approximately","around","estimate"}
COMMIT = {"will","shall","must","decided","announced","approved","reduces","increases","commits","confirms"}

def _pull_dates(text: str) -> List[str]:
    hits, out = [], []
    for m in re.finditer(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}|\b\d{4}-\d{2}-\d{2}', text, re.I):
        s = m.group(0)
        try:
            hits.append(dparser.parse(s, fuzzy=True).date().isoformat())
        except Exception:
            pass
    for h in hits:
        if h not in out:
            out.append(h)
    return out

def _pull_entities_light(text: str) -> Dict[str, List[str]]:
    ents = {"ORG":[], "PERSON":[], "GPE":[]}
    for m in regex.finditer(r'\b([A-Z][A-Za-z&.\-]+(?:\s+[A-Z][A-Za-z&.\-]+){0,3})\b', text):
        span = m.group(1)
        if len(span.split())==1 and span.isupper():
            continue
        low = span.lower()
        if any(k in low for k in ["federal","board","university","bank","department","ministry","committee","corp","inc","ltd"]):
            if span not in ents["ORG"]: ents["ORG"].append(span)
        elif any(k in low for k in ["states","republic","kingdom","city","province","county"]):
            if span not in ents["GPE"]: ents["GPE"].append(span)
        else:
            if span not in ents["PERSON"]: ents["PERSON"].append(span)
    return ents

def _pull_quotes(text: str) -> List[Dict[str, Any]]:
    out=[]
    for m in RE_QUOTE.finditer(text):
        q = m.group(1) or m.group(2)
        out.append({"text": q.strip(), "speaker": None, "char_span": [m.start(), m.end()]})
    return out

def _keyword_top(text: str, k: int = 10) -> List[str]:
    words = [w.lower() for w in regex.findall(r'[a-zA-Z][a-zA-Z\-]{2,}', text)]
    stop = set("the a an and or if in on of to for with by as from this that these those be is are was were been being about between into after before during over under up down out more most less least such than not no nor".split())
    freq={}
    for w in words:
        if w in stop: continue
        freq[w]=freq.get(w,0)+1
    ranked = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [w for w,_ in ranked[:k]]

def _modality_scores(text: str) -> Dict[str, Any]:
    tokens = [t.lower() for t in regex.findall(r"[a-zA-Z']+", text)]
    hed = {h:0 for h in HEDGE}; com={c:0 for c in COMMIT}
    for t in tokens:
        if t in hed: hed[t]+=1
        if t in com: com[t]+=1
    hsum = sum(hed.values()); csum = sum(com.values())
    stance = 0.0 if (hsum+csum)==0 else csum/(hsum+csum)
    return {
        "hedges":[{"term":k,"count":v} for k,v in hed.items() if v],
        "commit":[{"term":k,"count":v} for k,v in com.items() if v],
        "stance_index": round(stance, 2)
    }

def _fact_pack(text: str) -> Dict[str, Any]:
    return {
        "dates": _pull_dates(text),
        "money": list(dict.fromkeys(RE_MONEY.findall(text))),
        "percents": list(dict.fromkeys(RE_PERCENT.findall(text))),
        "numbers": list(dict.fromkeys(RE_NUMBER.findall(text))),
        "tickers": [t for t in set(RE_TICKER.findall(text)) if len(t)>=2 and not t.isdigit()],
        "entities": _pull_entities_light(text)
    }

# ------------------------- Core API -----------------------------------------
def analyze_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    document:v1 -> analysis:v1
    """
    validate_document(doc)

    raw_text = doc["content"]["text"]
    text = _normalize_text(raw_text)
    sections = _split_sections(text)
    words = len(text.split())

    analysis = {
        "schema": "analysis:v1",
        "meta": {
            "title": (doc.get("meta") or {}).get("title"),
            "url": (doc.get("meta") or {}).get("url"),
            "source_created_at": (doc.get("meta") or {}).get("created_at"),
            "analyzed_at": _now_iso(),
        },
        "stats": {
            "chars": len(text),
            "words": words,
            "lines": len(text.splitlines()),
            "reading_minutes": round(words/230.0, 2),
        },
        "sections": sections,
        "facts": _fact_pack(text),
        "quotes": _pull_quotes(text),
        "modality": _modality_scores(text),
        "keywords": _keyword_top(text, k=12),
        "hash": _sha256(text),
        "version": ANALYSIS_VERSION,
    }
    return analysis

# ------------------------- CLI ----------------------------------------------
# Usage:
#   cat doc.json | python nlp_layer.py
#   python nlp_layer.py --in doc.json --out analysis.json
def _cli():
    import argparse
    ap = argparse.ArgumentParser(description="document:v1 -> analysis:v1 (LLM-free)")
    ap.add_argument("--in", dest="inpath", help="Path to document:v1 JSON; omit to read STDIN")
    ap.add_argument("--out", dest="outpath", help="Write analysis JSON to file; omit to STDOUT")
    args = ap.parse_args()

    raw = sys.stdin.read() if not args.inpath else open(args.inpath, "r", encoding="utf-8").read()
    doc = json.loads(raw)
    analysis = analyze_document(doc)

    if args.outpath:
        with open(args.outpath, "w", encoding="utf-8") as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)
        print(f"[nlp] wrote {args.outpath}")
    else:
        print(json.dumps(analysis, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    _cli()
