# url_ingest.py
import requests, hashlib, time
from bs4 import BeautifulSoup
from readability import Document

UA = {"User-Agent": "NoiseToSignal/ingest-1.0"}

def ingest_url(url: str) -> dict:
    """Fetch, extract, and wrap content from a URL."""
    print("[ingest] Fetching URL...")
    r = requests.get(url, headers=UA, timeout=15)
    r.raise_for_status()
    html = r.text

    print("[ingest] Extracting main content...")
    doc = Document(html)
    title = (doc.short_title() or "").strip() or None
    main_html = doc.summary(html_partial=True)
    soup = BeautifulSoup(main_html, "lxml")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    text = soup.get_text("\n").strip()

    print("[ingest] Wrapping payload...")
    digest = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
    payload = {
        "source": {
            "url": url,
            "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        },
        "meta": {"title": title, "html_bytes": len(html.encode("utf-8"))},
        "content": {"text": text},
        "hash": digest,
        "version": "ingest:1.0.0"
    }
    return payload
