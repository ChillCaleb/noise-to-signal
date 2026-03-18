#!/usr/bin/env python3

import argparse
import json
import sys
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.metrics_schema import EvaluationConfig
from evaluation.runner import run_batch_evaluation


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark one dataset across model/tier/length configs.")
    parser.add_argument("--dataset", required=True, help="CSV, JSON, or JSONL dataset with article text.")
    parser.add_argument("--outdir", default="artifacts/evaluation/benchmarks")
    parser.add_argument("--providers", nargs="+", default=["groq"])
    parser.add_argument("--models", nargs="+", default=[""])
    parser.add_argument("--model-names", nargs="+", default=["groq"])
    parser.add_argument("--tiers", nargs="+", default=["tier1", "tier2"])
    parser.add_argument("--lengths", nargs="+", default=["short", "medium"])
    parser.add_argument("--summac-model", default="conv", choices=["conv", "zs"])
    parser.add_argument("--with-factcc", action="store_true")
    parser.add_argument("--stability-runs", type=int, default=1)
    parser.add_argument("--carbon-dir", default="artifacts/evaluation")
    args = parser.parse_args()

    outputs = []
    for provider, provider_model, model_name, tier, length in product(
        args.providers, args.models, args.model_names, args.tiers, args.lengths
    ):
        config = EvaluationConfig(
            tier=tier,
            output_format="text",
            length=length,
            model_name=model_name,
            provider=provider,
            provider_model=provider_model or None,
            include_factcc=args.with_factcc,
            summac_model=args.summac_model,
            stability_runs=max(args.stability_runs, 1),
            carbon_output_dir=args.carbon_dir,
        )
        model_slug = provider_model or "default"
        run_dir = f"{args.outdir}/{provider}_{model_slug}_{model_name}_{tier}_{length}"
        result = run_batch_evaluation(
            dataset_path=args.dataset,
            config=config,
            output_dir=run_dir,
        )
        outputs.append(
            {
                "provider": provider,
                "provider_model": provider_model or None,
                "model_name": model_name,
                "tier": tier,
                "length": length,
                "paths": result,
            }
        )

    print(json.dumps(outputs, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
