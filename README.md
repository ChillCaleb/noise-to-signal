# Noise to Signal

## Run The App

Multipage app:

```bash
python3 main_env.py app
```

Direct Streamlit entrypoints:

```bash
streamlit run app/home.py
streamlit run streamlit_app.py
```

The new evaluation UI is available from the multipage app as the `Evaluation` page, and the single-file `streamlit_app.py` now renders the same comparison view directly.

## Chrome Extension MVP

This repo now includes a local Chrome extension under `extension/` plus a FastAPI backend under `api/`.

Start the backend:

```bash
pip install -r requirements.txt
cp .env.example .env
# add GROQ_API_KEY to .env
python -m uvicorn api.server:app --reload --host 0.0.0.0 --port 8000
```

Then load the extension:

1. Open `chrome://extensions`.
2. Enable Developer mode.
3. Click `Load unpacked`.
4. Select the `extension/` directory.
5. Open an article and click the Noise to Signal toolbar button.

The extension reads the active page where Chrome permits it, sends the article text or URL to `POST /api/analyze`, displays the summary/signals in the side panel, and saves recent runs to `data/noise_to_signal_extension.db`.

If the backend is running in GitHub Codespaces, forward port `8000` and paste the forwarded `https://...app.github.dev` URL into the extension's Backend field.

## Evaluation Harness

This repo now includes a modular evaluation harness that wraps the existing pipeline instead of replacing it.

The harness reuses:
- `adapter_input.py` for `document:v1`
- `nlp_layer.py` for `analysis:v1`
- `llm_layer.py` via `main.py` helpers for summary generation

New evaluation modules live in `evaluation/`:
- `summac_eval.py`: SummaC wrapper with configurable `SummaCConv` or `SummaCZS`
- `factcc_eval.py`: optional FactCC adapter plus prepared `jsonl` export for checkpoint-based workflows
- `carbon_eval.py`: CodeCarbon tracking helpers
- `stability.py`: repeated-run stability metrics
- `runner.py`: single and batch orchestration

### Setup

Core repo dependencies remain in `requirements.txt`.

Evaluation extras are isolated in `requirements-eval.txt`:

```bash
pip install -r requirements.txt
pip install -r requirements-eval.txt
```

Notes:
- SummaC is wrapped behind `evaluation/summac_eval.py` and defaults to `SummaCConv` on CPU if CUDA is unavailable.
- The first live SummaC run downloads the convolution checkpoint plus Hugging Face model weights, so the initial evaluation can take a few minutes on CPU.
- CodeCarbon is used in offline mode by default and writes emissions CSV files under `artifacts/evaluation/`.
- OpenAI comparison is optional and uses `OPENAI_API_KEY` plus `OPENAI_MODEL` if you want to override the default.
- FactCC is intentionally pluggable. If `FACTCC_CHECKPOINT_PATH` and `FACTCC_EVAL_SCRIPT` are set, the harness will try local subprocess inference; otherwise it falls back to Hugging Face inference with `manueldeprada/FactCC`.

### Single Article Evaluation

Evaluate a URL:

```bash
python3 scripts/evaluate_single.py \
  --input "https://example.com/article" \
  --tier tier1 \
  --length short \
  --outdir artifacts/evaluation/single
```

Evaluate a saved artifact:

```bash
python3 scripts/evaluate_single.py \
  --artifact data/document.json \
  --stability-runs 3 \
  --with-factcc
```

Evaluate an existing model output without calling Groq:

```bash
python3 scripts/evaluate_single.py \
  --artifact data/document.json \
  --summary-file data/llm_output.txt
```

Outputs:
- one structured JSON result per run
- CodeCarbon emissions CSV under `artifacts/evaluation/<run_id>/emissions.csv`
- optional FactCC input artifact under the selected output directory

### Batch Evaluation

Run over a dataset:

```bash
python3 scripts/evaluate_batch.py \
  --dataset data/articles_raw.jsonl \
  --tier tier1 \
  --length short \
  --outdir artifacts/evaluation/batch
```

Run over saved JSON article artifacts:

```bash
python3 scripts/evaluate_batch.py \
  --artifact-dir data/articles \
  --outdir artifacts/evaluation/batch
```

Batch outputs:
- `results.jsonl`
- `results.csv`
- emissions CSV files under `artifacts/evaluation/`

If your dataset already includes `summary_text` or `summary`, batch evaluation will score that text directly and skip generation for those rows.

### Benchmark Multiple Configurations

```bash
python3 scripts/benchmark_models.py \
  --dataset data/articles_raw.jsonl \
  --model-names groq \
  --tiers tier1 tier2 \
  --lengths short medium
```

### Result Shape

Each evaluation result is stored in an analysis-friendly structure:

```json
{
  "article_id": "...",
  "source_url": "...",
  "model_name": "groq",
  "run_id": "...",
  "summary_text": "...",
  "metrics": {
    "summac": {},
    "factcc": {},
    "stability": {},
    "compute": {}
  },
  "meta": {
    "timestamp": "...",
    "tier": "tier1",
    "output_format": "text",
    "length": "short"
  }
}
```

### FactCC Next Step

If you want live FactCC scoring with the legacy Salesforce workflow, provide the checkpoint paths in your environment:

```bash
export FACTCC_CHECKPOINT_PATH=/path/to/model.ckpt
export FACTCC_EVAL_SCRIPT=/path/to/factCC/evaluate.py
export FACTCC_PYTHON_BIN=python3
```

With those set:
- the evaluation runner will try local FactCC subprocess inference
- the Streamlit evaluation page will show a `FactCC` metric beside `SummaC`
- if either path is missing, the system falls back to Hugging Face inference using `manueldeprada/FactCC`

Optional override:

```bash
export FACTCC_HF_MODEL=manueldeprada/FactCC
```

The adapter still isolates the integration point in one module: [evaluation/factcc_eval.py](/Users/calebbanks/noise-to-signal/evaluation/factcc_eval.py).
