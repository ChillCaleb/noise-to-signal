# main.py
# Input -> (URL ingest | text adapter) -> NLP -> LLM(Groq) -> save + print
# Artifacts: ./data/document.json, ./data/analysis.json, ./data/llm_output.(txt|html)

import argparse, os, json

def build_document_from_url(url: str) -> dict:
    # Lazy imports prevent import-time side effects
    from url_ingest import ingest_url
    from adapter_input import to_document
    ingest = ingest_url(url)
    text   = ingest["content"]["text"]
    title  = (ingest.get("meta") or {}).get("title")
    src    = (ingest.get("source") or {}).get("url")
    return to_document(text=text, title=title, url=src)  # document:v1

def build_document_from_text(txt: str) -> dict:
    from adapter_input import to_document
    return to_document(text=txt, title=None, url=None)   # document:v1

def run_nlp(document: dict) -> dict:
    from nlp_layer import analyze_document
    return analyze_document(document)                    # analysis:v1

def run_llm(analysis: dict, tier: str, output_format: str, length: str) -> str:
    from llm_layer import summarize
    return summarize(analysis, tier=tier, output_format=output_format, length=length)

def save_json(obj: dict, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print(f"[main] wrote {path}")

def save_text(s: str, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)
    print(f"[main] wrote {path}")

def main():
    ap = argparse.ArgumentParser(description="Noise-to-Signal runner")
    ap.add_argument("--input", help="URL or plain text. If omitted, you’ll be prompted.")
    ap.add_argument("--outdir", default="data", help="Where to write artifacts.")
    ap.add_argument("--tier", default="tier1", choices=["tier1","tier2"], help="LLM tier.")
    ap.add_argument("--format", default="text", choices=["text","html"], help="LLM output format.")
    ap.add_argument("--length", default="short", choices=["short","medium","long"], help="LLM length hint.")
    args = ap.parse_args()

    user_input = args.input if args.input is not None else input("Enter a URL or paste text, then press Enter:\n> ")
    user_input = (user_input or "").strip()
    if not user_input:
        raise ValueError("Empty input.")

    # 1) Input -> document:v1
    if user_input.startswith(("http://","https://")):
        print("[main] Detected URL -> url_ingest -> document")
        document = build_document_from_url(user_input)
    else:
        print("[main] Detected plain text -> adapter_input -> document")
        document = build_document_from_text(user_input)

    doc_path = os.path.join(args.outdir, "document.json")
    save_json(document, doc_path)

    # 2) NLP -> analysis:v1
    analysis = run_nlp(document)
    ana_path = os.path.join(args.outdir, "analysis.json")
    save_json(analysis, ana_path)

    # 3) LLM(Groq) -> final text/html
    llm_output = run_llm(analysis, tier=args.tier, output_format=args.format, length=args.length)
    ext = "html" if args.format == "html" else "txt"
    llm_path = os.path.join(args.outdir, f"llm_output.{ext}")
    save_text(llm_output, llm_path)

    # 4) Quick console peek
    title = (analysis.get("meta") or {}).get("title")
    words = (analysis.get("stats") or {}).get("words")
    print(f"[main] title: {title!r} | words: {words} | tier: {args.tier} | format: {args.format}")
    preview = llm_output[:240].replace("\n", " ")
    print(f"[llm] preview: {preview}...")

if __name__ == "__main__":
    main()
