#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.metrics_schema import EvaluationConfig
from evaluation.runner import evaluate_summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a single article or saved artifact.")
    parser.add_argument("--input", help="URL or raw article text.")
    parser.add_argument("--artifact", help="Path to document:v1, analysis:v1, or article JSON artifact.")
    parser.add_argument("--summary-text", help="Use an existing summary instead of generating one.")
    parser.add_argument("--summary-file", help="Read an existing summary from a text file.")
    parser.add_argument("--outdir", default="artifacts/evaluation/single")
    parser.add_argument("--tier", default="tier1", choices=["tier1", "tier2"])
    parser.add_argument("--format", default="text", choices=["text", "html"])
    parser.add_argument("--length", default="short", choices=["short", "medium", "long"])
    parser.add_argument("--provider", default="groq", choices=["groq", "openai"])
    parser.add_argument("--model", default=None, help="Provider-specific model override.")
    parser.add_argument("--model-name", default="groq")
    parser.add_argument("--summac-model", default="conv", choices=["conv", "zs"])
    parser.add_argument("--summac-device", default=None)
    parser.add_argument("--with-factcc", action="store_true")
    parser.add_argument("--factcc-mode", default="placeholder", choices=["placeholder", "subprocess"])
    parser.add_argument("--stability-runs", type=int, default=1)
    parser.add_argument("--carbon-dir", default="artifacts/evaluation")
    args = parser.parse_args()

    if not args.input and not args.artifact:
        parser.error("Provide --input or --artifact.")
    if args.summary_text and args.summary_file:
        parser.error("Use either --summary-text or --summary-file, not both.")

    summary_text_override = args.summary_text
    if args.summary_file:
        summary_text_override = Path(args.summary_file).read_text(encoding="utf-8")

    config = EvaluationConfig(
        tier=args.tier,
        output_format=args.format,
        length=args.length,
        model_name=args.model_name,
        provider=args.provider,
        provider_model=args.model,
        include_factcc=args.with_factcc,
        summac_model=args.summac_model,
        summac_device=args.summac_device,
        factcc_mode=args.factcc_mode,
        stability_runs=max(args.stability_runs, 1),
        carbon_output_dir=args.carbon_dir,
    )
    result = evaluate_summary(
        input_text_or_url=args.input,
        artifact_path=args.artifact,
        config=config,
        output_dir=args.outdir,
        summary_text_override=summary_text_override,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
