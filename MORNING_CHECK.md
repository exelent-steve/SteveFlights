# Morning Flight Check — Runbook

When Steve says "check flights" (or similar), Claude runs this. No scheduler —
it's on-demand. Needs Steve's Chrome open (the claude-in-chrome extension).

## Steve's firm constraints

- **Route:** TLV ⇄ UK. **Liverpool (LPL) preferred**; Manchester (MAN) fine;
  **mixing airports is allowed** (e.g. in LPL, out MAN — ~35 min apart).
- **Outbound:** no earlier than 26 Jul 2026 (and not in the past).
- **No travel on Friday or Saturday** (Shabbat — delay risk). 2026 blocked travel
  days: 31 Jul, 1 Aug, 7 Aug, 8 Aug.
- **Stay:** 5–8 nights. **Return by 12 Aug.**
- **1 connection max**, layover **2–6h**, **NO overnight layover**, no 1am-ish arrivals.
- **2 travellers** (Steve + 16yo, both adults). Prices in NIS.
- Target was ~1,600 pp round-trip (currently unrealistic — see watchlog).

## Procedure

1. Generate today's URLs:
   ```bash
   python3 gen_searches.py            # QUICK: ~5 sweet-spot date pairs
   python3 gen_searches.py --full     # FULL: every valid date pair (slow)
   ```
2. **Kiwi.com first** (fastest — one search covers BOTH airports, with
   1-stop+no-overnight already applied via `stopNumber=1~false&sortBy=price`):
   for each KIWI URL — `navigate`, wait ~9s, run `extract_kiwi.js`. The top
   cards are the cheapest compliant options. (Don't return the URL in JS output —
   the harness blocks query-string data.)
3. **Skyscanner as cross-check / deeper read** (per airport): for each round-trip
   URL — `navigate`, wait ~6s, run `extract_options.js`, read "Flight option" blocks.
4. From both sources, find the cheapest option meeting ALL constraints: 1 stop,
   no overnight layover (watch "+1" / "one day later" with long duration), layover
   2–6h, sane arrival. Note price + times. Cross-check that Kiwi & Skyscanner agree.
5. Append one line per run to `watchlog.md` (date, best COMPLIANT price + route +
   times + source, and the absolute-cheapest for trend).
6. Tell Steve: best compliant option today, and whether it beat previous days.
   **Flag loudly if a compliant round-trip drops under ~₪1,800 pp** — that's a
   real deal worth booking fast (self-transfers via Kiwi/MyTrip "Select" give a
   connection guarantee).

### Tip: keep it fast
Kiwi covers both airports per search, so the ~5 Kiwi URLs are the core daily scan
(~2 min). Only open the Skyscanner per-airport pages when Kiwi shows something
promising, or every few days as a cross-check.

## Notes / gotchas

- **Date-bar "cheapest per day" prices LIE** — they're 14–23h overnight ordeals.
  Only trust the detailed "Flight option" blocks.
- Google Flights / `flights.py` does NOT show self-transfers — don't rely on it
  for this trip. Skyscanner-in-Chrome is the real engine.
- Skyscanner blocks plain HTTP (403) and its internal API tokens expire — must
  read the DOM in the live browser tab.
