from typing import List, Optional, Tuple
import pandas as pd
try:
    import spacy
    _nlp = spacy.load("en_core_web_sm")
except Exception:
    _nlp = None

from rapidfuzz import process

_symbols = pd.read_csv("data/symbols.csv")
_company_list = _symbols["company"].tolist()

def extract_orgs(text: str) -> List[str]:
    if _nlp is None:
        # minimal fallback: return capitalized tokens  (very naive)
        return []
    doc = _nlp(text)
    return [ent.text for ent in doc.ents if ent.label_ in ("ORG","PRODUCT")]

def match_company_to_ticker(company: str, score_cutoff: int = 85) -> Optional[Tuple[str, str]]:
    # returns (ticker, company_match) or None
    match = process.extractOne(company, _company_list, score_cutoff=score_cutoff)
    if not match:
        return None
    matched_name = match[0]
    row = _symbols[_symbols["company"] == matched_name].iloc[0]
    return row["ticker"], matched_name

def link_text_to_tickers(text: str) -> List[str]:
    tickers = set()
    for org in extract_orgs(text):
        res = match_company_to_ticker(org)
        if res:
            tickers.add(res[0])
    return sorted(tickers)
