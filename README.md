# Smart Router + Multi-Critic Arbitration Pipeline

**X% cost reduction** vs always routing to the top model · **catches Y% of errors** that single-model self-checks miss

> Fill in **X** and **Y** after you run the Phase 6 batch + planted-case evaluation (see below). Until then, leave them as placeholders in your portfolio write-up.

Routes each LLM request to the cheapest capable model, cheaply self-checks quality, and escalates to a multi-critic jury only when the check smells trouble.

> **Provider:** All LLM calls go through **OpenRouter** (`OPENROUTER_API_KEY`) via `https://openrouter.ai/api/v1`.

## Status

- [x] Phase 0 — Foundations
- [x] Phase 1 — Unified model interface
- [x] Phase 2 — Complexity classifier & routing
- [x] Phase 3 — Cheap single-judge verifier
- [x] Phase 4 — Full multi-critic arbitration
- [x] Phase 5 — Logging, dashboard, API
- [x] Phase 6 — Portfolio polish

## Setup (local)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # paste OPENROUTER_API_KEY from https://openrouter.ai/keys
python -m src.routing.train_classifier
```

Always run Python from the repo root so `src.*` imports resolve.

## Run API + dashboard

```bash
# terminal 1
uvicorn src.api.main:app --reload --host 127.0.0.1 --port 8000

# terminal 2
streamlit run src/dashboard/app.py
```

```bash
curl -s -X POST http://127.0.0.1:8000/v1/completions \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"What is the capital of France?"}' | python -m json.tool
```

## Phase 6 — portfolio numbers

### 1) Cost-reduction batch (500+ prompts)

Route-only (recommended for the **X%** headline — affordable):

```bash
python scripts/run_batch_benchmark.py --limit 520
```

Full pipeline on a smaller sample (route + verify + maybe arbitrate — costly):

```bash
python scripts/run_batch_benchmark.py --limit 50 --full
```

**Where to find numbers**

| Artifact | Path |
|----------|------|
| Headline summary | `data/batch_summary.json` → `cost_reduction_pct`, `cost_saved_usd`, `total_cost_usd`, `total_baseline_cost_usd` |
| Per-prompt rows | `data/batch_results.json` |
| Prompt list | `data/batch_prompts.csv` |
| Live SQLite / dashboard | `data/router.db` · Streamlit **Cost view** · `GET /v1/stats` |

Copy `cost_reduction_pct` into the README hero as **X**.

### 2) Planted arbitration cases (screenshots)

Four cases live in `tests/test_cases/`:

1. `01_factually_wrong.json`
2. `02_logically_broken.json`
3. `03_misses_the_point.json`
4. `04_genuinely_good.json`

```bash
# local graph (no server required)
python scripts/run_planted_cases.py

# or via API
python scripts/run_planted_cases.py --api http://127.0.0.1:8000
```

Results land in `data/planted_results/*.json` — screenshot those or the dashboard **Verdict explorer**.

For **Y%** (errors single-judge misses that the full jury catches), compare single-judge vs arbitration on the three bad cases and record the method in `data/portfolio_metrics.example.yaml`.

## Docker

Requires a filled-in `.env` with `OPENROUTER_API_KEY` (never commit it).

```bash
docker compose up --build
```

- API: http://127.0.0.1:8000/health
- Dashboard: http://127.0.0.1:8501

Verify:

```bash
curl -s http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/v1/completions \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"What is 2+2?"}' | python -m json.tool
```

Both services share `./data` so dashboard rows match API writes.

## Architecture (short)

```
Request → complexity classifier → cheapest capable model → response
                ↓ (async)
         cheap single-judge verify
                ↓ on DISAGREE only
         3 critics (parallel LangGraph) → adjudicator → verdict
```

## Repo layout

```
llm-router-arbitration/
├── docker-compose.yml
├── Dockerfile
├── README.md
├── requirements.txt
├── config/routing.yaml
├── scripts/
│   ├── run_batch_benchmark.py
│   ├── run_planted_cases.py
│   └── smoke_openrouter.py
├── src/
│   ├── models/
│   ├── routing/
│   ├── verification/
│   ├── arbitration/
│   ├── storage/
│   ├── api/
│   └── dashboard/
├── data/
└── tests/test_cases/
```
