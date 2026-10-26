# WindDesk

A web app that helps a GB energy utility's day-ahead trading team answer two questions about national wind generation:

1. **What is the latest wind forecast I could see when I place the day-ahead order?**
2. **How accurate are those forecasts, so I can size my cover?**

Data comes only from Elexon (BMRS): actuals from `FUELHH` (`fuelType = WIND`) and forecasts from `WINDFOR`.
Scope is purchase decisions taken in **January 2026** (delivery days 2 Jan to 1 Feb 2026).

- Live app: **https://kjhwr-ten.vercel.app/**
- Stack: React (Vite, Recharts) + Python (FastAPI, pandas), Docker, deployed on Vercel.

> **AI tools disclosure:** this project was built with the help of an AI assistant (Anthropic Claude) for code generation, design and documentation. The logic, assumptions and results were reviewed before submission.

---

## How the key logic works

Each target half-hour (`startTime`) has many forecast versions, each with a different `publishTime`.

* **Decision cutoff:** for delivery day `D`, the order is placed on `D-1` at a configurable UK local time (default **09:00**).
* **Latest forecast available:** for each half-hour, take the forecast with the largest `publishTime` that is `<= cutoff`. Forecasts published later are ignored because the buyer could not have seen them.
* **Alternative rule:** "fixed lead time" picks the newest forecast published at least *N* hours before the target.
* **Error** = forecast − actual. Positive means over-forecast (wind came in lower, so the buyer is short).
* **Metrics:** MAE, RMSE, bias, MAPE (ignoring periods under 500 MW), P50/P90/P95/P99 of absolute error, share of over-forecasts, daily metrics, error histogram, and accuracy by forecast horizon (`startTime − publishTime`, using every forecast version).

### Assumptions

| Topic                       | Assumption                                                                                                    |
| --------------------------- | ------------------------------------------------------------------------------------------------------------- |
| "Decisions in January 2026" | Decisions are taken on 1 to 31 Jan, so delivery days are 2 Jan to 1 Feb. Change in `backend/app/config.py`. |
| Cutoff                      | 09:00 UK local time on D-1, configurable in the UI and via `DEFAULT_CUTOFF`.                                |
| Time zone                   | All data is stored in UTC. Delivery day and cutoff use `Europe/London`, so BST/GMT is handled.              |
| Forecast history            | Forecasts published from 18 Dec 2025 are fetched, because early-January targets are forecast ~2 weeks ahead.  |
| Units                       | MW per half-hour. Energy (MWh) = MW × 0.5 summed over the day.                                               |
| Capacity                    | No installed-capacity data is used (Elexon only), so percentage errors are relative to actual output.         |

---

## Files and directories

```
.
├── backend/
│   ├── app/
│   │   ├── config.py      Settings: date scope, timezone, default cutoff
│   │   ├── elexon.py      Elexon BMRS client (chunked, retrying, auto-splits large windows)
│   │   ├── store.py       In-memory data store + gzip-CSV snapshot on disk
│   │   ├── forecast.py    Core logic: forecast selection, join with actuals, metrics, insights
│   │   ├── main.py        FastAPI routes
│   │   └── demo.py        Synthetic data generator (offline UI work only, never real)
│   ├── scripts/fetch_data.py   Download the January 2026 snapshot into backend/data
│   ├── tests/test_forecast.py  Unit tests for the selection logic and metrics
│   ├── data/              Snapshot lives here (actuals.csv.gz, forecasts.csv.gz, meta.json)
│   ├── Dockerfile
│   └── requirements*.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx            App shell, global controls, loading states
│   │   ├── api.js             API client and `useAsync` hook
│   │   ├── format.js          UK-time and number formatting
│   │   ├── styles.css         Design tokens and layout
│   │   └── components/        DayBrief, Accuracy, Controls, Tip (tooltip)
│   ├── Dockerfile, nginx.conf
│   └── package.json, vite.config.js
├── api/index.py        Vercel serverless entrypoint (re-exports the FastAPI app)
├── vercel.json         Vercel build + routing
├── requirements.txt    Python deps used by Vercel
├── docker-compose.yml
└── docs/video-script.md   Talking points for the demo video
```

## API

| Endpoint                                                                           | Purpose                                                       |
| ---------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| `GET /api/meta`                                                                  | Data status, scope, default cutoff                            |
| `GET /api/actuals?start&end`                                                     | Actual wind generation                                        |
| `GET /api/forecast/latest?start&end&mode=cutoff\|lead&cutoff=09:00&lead_hours=24` | Selected forecast joined with actuals, plus per-day summaries |
| `GET /api/metrics?...same params`                                                | Overall metrics, daily metrics, histogram, insights           |
| `GET /api/horizon-metrics?start&end`                                             | Accuracy by forecast horizon                                  |
| `POST /api/refresh`                                                              | Re-download from Elexon (disabled on Vercel)                  |

Interactive docs: `/docs` on the backend.

---

## Run it

### 1. Get the data (needs internet access to Elexon)

```bash
cd backend
pip install -r requirements-dev.txt
python scripts/fetch_data.py        # writes backend/data/*.csv.gz
```

This takes a minute or two. Commit the three files in `backend/data/` so the Vercel deployment can serve them.

### 2a. With Docker

```bash
docker compose up --build
```

Open http://localhost:8080 (API at http://localhost:8000/docs). If `backend/data` is empty the backend fetches from Elexon on first start and the UI shows a progress message.

### 2b. Without Docker

```bash
# terminal 1
cd backend && uvicorn app.main:app --reload --port 8000
# terminal 2
cd frontend && npm install && npm run dev      # http://localhost:5173
```

### Tests

```bash
cd backend && python -m pytest
```

### Offline preview with fake data

`python scripts/fetch_data.py --demo` writes **synthetic** data and the UI shows a "Demo data" banner. Never use it for the real analysis.

---

## Deploy on Vercel (single project)

1. Run the fetch script and commit `backend/data/`.
2. Push to GitHub and import the repo in Vercel (no framework preset needed; `vercel.json` handles it).
3. The static React build is served from `frontend/dist` and the API runs as a Python function at `/api/*`.

Vercel's filesystem is read-only, so the deployed app serves the committed snapshot and `/api/refresh` is disabled there.

## Design notes

* The API never calls Elexon per request: data is cached in memory and persisted as a snapshot.
* The selection logic is a pure function (`select_latest_before_cutoff`) with unit tests for the cutoff boundary, per-day cutoffs, BST handling and lead-time mode.
* The "planning range" in the day brief is the forecast ± the 90th percentile absolute error for the same selection rule.
