# SteveFlights

Personal tool to find the cheapest **Tel Aviv ⇄ UK (Liverpool/Manchester)**
flights for a family trip in summer 2026, and to check prices day-by-day so we
catch a deal when one appears.

## If the user says "check flights" / "morning check" — follow MORNING_CHECK.md

That runbook is the source of truth. Quick version:
1. `python3 gen_searches.py` → today's valid URLs (QUICK mode), both Kiwi + Skyscanner.
2. Drive the user's Chrome (claude-in-chrome). **Kiwi first** (one search = both
   airports, 1-stop+no-overnight pre-applied): navigate to each KIWI url, wait ~9s,
   run `extract_kiwi.js`. Then **Skyscanner** per airport as cross-check: navigate,
   run `extract_options.js`, read "Flight option" blocks.
   (Don't return the page URL from JS — the harness blocks query-string output.)
3. Find the cheapest option meeting ALL constraints (below). Note price + times.
4. Append a line to `watchlog.md`. Report best compliant option + trend vs prior days.

## Firm constraints (do not relax without asking)

- TLV ⇄ UK. **Liverpool (LPL) preferred**, Manchester (MAN) fine, **mixing airports OK**.
- Outbound **no earlier than 26 Jul 2026** (and not in the past).
- **No travel Friday or Saturday** (Shabbat). 2026 blocked: 31 Jul, 1, 7, 8 Aug.
- Stay **5–8 nights**, return **by 12 Aug**.
- **1 connection max**, layover **2–6h**, **NO overnight layover**, no ~1am arrivals.
- **2 travellers** (Steve + 16yo, both adults). Prices in **NIS**.
- Old target ~₪1,600 pp RT — currently unrealistic (see watchlog).

## Hard-won lessons (don't repeat these mistakes)

- **Skyscanner is the engine**, scraped via the Chrome extension. It blocks plain
  HTTP (403) and its internal API tokens expire — must read the live DOM
  (`document.body.innerText`, parse "Flight option N:" blocks).
- **Date-bar "cheapest per day" prices LIE** — they're 14–23h overnight self-transfer
  ordeals. Only trust the detailed per-option text.
- **Google Flights / `flights.py` does NOT show self-transfers** — wrong engine for
  this trip; every viable option here is a self-transfer. Don't rely on it.
- Kiwi.com / Tequila API and TripStack/MyTrip are affiliate/B2B-gated — no usable
  public API. **Kiwi.com's consumer website** is a good *second* scrape source.
- Self-transfers booked via Skyscanner's "Select" → Kiwi/MyTrip get a connection
  guarantee (rebook if leg 1 is late) — the safe way to book these.

## Files

- `gen_searches.py` — emits valid Kiwi + Skyscanner URLs (--quick default, --full).
- `extract_kiwi.js` — DOM extractor for Kiwi result cards (ResultCardWrapper).
- `extract_options.js` — DOM extractor for Skyscanner "Flight option" blocks.
- `MORNING_CHECK.md` — the full runbook.
- `watchlog.md` — day-by-day price history (the thing that catches a drop).
- `flights.py` / `app.py` / `kiwi.py` / `config.py` — older Google-Flights + Kiwi
  attempt + Streamlit UI. Kept, but NOT the engine for this trip (see lessons).
