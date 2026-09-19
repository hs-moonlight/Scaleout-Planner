# Scale-Out Planner - Backend (Step 2)

FastAPI backend for the trailing-stop scale-out strategy: the scale-out math,
a technical **fair-entry zone** with analyst consensus, and local trade
persistence (save a plan, come back to record fills, review results).

Advisory only - it calculates prices and stores trades; it does not place orders.

## Run locally

```bash
cd backend
python -m venv .venv
# Windows:  .venv\Scripts\activate       macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env      # macOS/Linux: cp .env.example .env
# edit .env and add your API keys (see below)
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs for the interactive API docs.

Requires Python 3.10+ (3.11/3.12/3.13/3.14 all fine).

## API keys (free tiers)

Put these in `.env`:

- `ALPHA_VANTAGE_API_KEY` - technicals (weekly ATR + SMA). Free key: https://www.alphavantage.co/support/#api-key
- `FMP_API_KEY` - quote (price + 50/200-day averages) and analyst consensus. https://financialmodelingprep.com/

`/plan` and the `/trades` endpoints work with no keys; `/quote`, `/analyst`, and
`/suggest` need them.

## Endpoints

| Method | Path | What |
|---|---|---|
| GET | `/health` | liveness check |
| POST | `/plan` | scale-out plan from investment + entry + stop % (no network) |
| GET | `/quote/{symbol}` | live price + 50/200-day averages |
| GET | `/analyst/{symbol}` | Buy/Hold/Sell consensus + price targets |
| GET | `/suggest/{symbol}?stop_pct=6` | fair-entry zone + flags (incl. stop-vs-ATR) + analyst overlay |
| POST | `/trades` | save a trade plan |
| GET | `/trades` | list saved trades |
| GET | `/trades/{id}` | one trade |
| PUT | `/trades/{id}` | update (record actual fills) |
| GET | `/trades/{id}/realized` | realized P&L / R / % from recorded fills |
| GET | `/trades/stats` | win rate + total realized R (journal foundation) |
| DELETE | `/trades/{id}` | delete a trade |

## Fair-entry logic (`/suggest`)

Builds a suggested entry **zone** (not one price) from: 40-week / ~200-day SMA
(trend anchor), 50-day / 10-week SMA (faster average), and weekly ATR
(volatility). Flags whether the trend is rising, whether price is extended above
the zone, and - key check - whether the stop distance is **tighter than one
weekly ATR** (i.e. inside normal noise and prone to random stop-outs). Not a buy
signal; you still enter your own fill.

## Tests

```bash
pytest                      # or, with no deps installed:
python tests/test_scaleout.py
```

## Roadmap context

Step 2 (this backend) runs locally with SQLite. Step 3 moves it to Azure
(App Service + PostgreSQL + Blob + Entra B2B guest auth). The auth layer is
built provider-agnostic and trades key on an internal `user_id`, so hosting/auth
can change without touching the strategy code. See the project build plan.
