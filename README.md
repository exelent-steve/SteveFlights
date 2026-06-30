# SteveFlights ✈️

Find the cheapest **Tel Aviv ⇄ Manchester/Liverpool** round-trips for the
summer trip, respecting connection rules, and re-run it often to catch
last-minute price drops.

It reads **Google Flights** for free via the [`fast-flights`](https://github.com/AWeirdDev/fast-flights)
library — which (unlike the Amadeus/RapidAPI options) includes the low-cost
carriers that actually make this route cheap.

## Setup (once)

```bash
cd ~/Documents/Github/SteveFlights
python3 -m pip install -r requirements.txt
```

## Run

```bash
python3 flights.py              # search with the defaults in config.py
python3 flights.py --top 15     # show more rows
python3 flights.py --max-price 7000   # only show trips at/under this TOTAL (NIS)
```

Each run prints a ranked table and saves a timestamped snapshot in `results/`.
On later runs it tells you whether the cheapest fare went **↓ down** or **↑ up**
since the previous check — so running it daily turns it into a deal tracker.

## Tweak the search

Everything lives in **`config.py`** — dates, length of stay, airports,
passengers, max stops, layover window, and the price you want flagged as a
✨ DEAL. Edit and re-run.

## How it reads the table

- Prices are the **TOTAL for the whole party** (`ADULTS` in config); `pp` = per person.
- ✅ `2-6h` = every connection respects your layover window.
- ⚠️ `breaks rule` = a layover is shorter than 2h or longer than 6h. These rows
  are shown anyway (usually they're the *cheapest*) so you can judge the
  trade-off — cheaper-but-overnight vs pricier-but-civilised.

## Honest limitations

- **Only 1-stop or nonstop** options are searched (per the brief). Many of the
  truly cheap TLV routings are 2-stop and are deliberately excluded.
- It searches each one-way leg separately and combines them. This gives full
  layover control and real LCC pricing, but can **miss legacy-carrier
  round-trip-only discounts** (rare on this route).
- Google sometimes returns only its top handful of options per query, so this
  finds the cheapest *visible* fares, not a guaranteed global minimum. Treat it
  as a fast daily radar, then book on the airline/Google directly.
- When a route returns "no ≤1-stop options found" (e.g. Liverpool right now),
  that's real: there simply aren't any while flights into Israel are reduced.

## Ideas for later

- Schedule it daily (cron / launchd) and have it text/email you on a price drop.
- Add Wizz Air's own site as a second source if/when it resumes TLV flying.
- Widen `OUT_DATES` for date flexibility.
