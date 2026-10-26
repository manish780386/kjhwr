# Video script (max 10 min total)

## Part 1: Client pitch (about 4:30)
1. **Problem (30s).** You buy tomorrow's power today. Wind is weather-driven, so you buy thermal to fill the gap. You need to know what forecast you can see at decision time, and how wrong it tends to be.
2. **Day-ahead brief (90s).** Open the app. Pick a day in the strip (bar height = forecast wind energy). Read the headline: expected GWh. Show peak, low and the forecast issue time versus the 09:00 cutoff. Toggle "Planning range" and explain the band. Toggle "Actual" to show the outcome afterwards.
3. **Change the rule (30s).** Switch the cutoff to 08:00 or to a fixed lead time and show the numbers move.
4. **Accuracy (90s).** Open "Forecast accuracy". Metric strip: average miss, bias, 9 in 10 within. Read the "What this means for buying" panel. Show the forecast-vs-actual chart with the orange miss gaps, and the day-by-day chart.
5. **Value close (30s).** Newest forecast beats older ones (show the horizon chart). The buffer in MW is a number they can plug into their hedging decision.

## Part 2: Tech lead review (about 4:30)
1. **Architecture (45s).** React + FastAPI. Elexon, then snapshot cache, then in-memory pandas, then JSON API.
2. **Core logic (90s).** Open `backend/app/forecast.py`. Walk through `cutoff_utc` (London time to UTC), `select_latest_before_cutoff` (filter publishTime <= cutoff, sort, keep last per startTime), and `build_comparison`.
3. **Metrics (45s).** `compute_metrics`, `horizon_metrics`, sign convention.
4. **Data layer (45s).** `elexon.py` chunking and auto-splitting, `store.py` snapshot, why Vercel serves a snapshot.
5. **Frontend (45s).** `App.jsx` state, `useAsync`, `DayBrief` and `Accuracy`.
6. **Practices (30s).** Run `pytest`, show `docker compose up`, README, assumptions table, AI usage disclosure.
