# adapter_input.py
# Purpose: Convert plain text (plus optional title/url) into a minimal, stable JSON
# schema that the NLP layer can always trust.

import sys, json, time
from typing import Optional, Dict

SCHEMA = "document:v1"

def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def to_document(text: str, title: Optional[str] = None, url: Optional[str] = None) -> Dict:
    """
    Plaintext -> Document JSON (schema: document:v1)

    Args:
        text: Required plain text content.
        title: Optional human title/headline.
        url: Optional source URL (if known).

    Returns:
        Dict shaped as:
        {
          "schema": "document:v1",
          "meta": { "title": <str|None>, "url": <str|None>, "created_at": <iso> },
          "content": { "text": <str> }
        }
    """
    if text is None:
        raise ValueError("text is required")
    text = str(text).strip()
    if not text:
        raise ValueError("text is empty after stripping")

    return {
        "schema": SCHEMA,
        "meta": {
            "title": (title.strip() if title else None) or None,
            "url": (url.strip() if url else None) or None,
            "created_at": _now_iso(),
        },
        "content": {
            "text": text
        }
    }

# --- CLI usage ---------------------------------------------------------------
# Examples:
#   echo "Some text" | python adapter_input.py
#   python adapter_input.py --text "Some text" --title "My Doc" --url "https://example.com" --out doc.json
def _cli():
    import argparse
    ap = argparse.ArgumentParser(description="Plaintext → document:v1 JSON")
    ap.add_argument("--text", help="Plain text. If omitted, read from STDIN.")
    ap.add_argument("--title", help="Optional title/headline", default=None)
    ap.add_argument("--url", help="Optional source URL", default=None)
    ap.add_argument("--out", help="Write to file instead of STDOUT", default=None)
    args = ap.parse_args()

    raw = args.text if args.text is not None else sys.stdin.read()
    doc = to_document(raw, title=args.title, url=args.url)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        print(f"[adapter] wrote {args.out}")
    else:
        print(json.dumps(doc, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    _cli()
