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
   python3 gen_searches.py            # QUICK: ~5 sweet-spot pairs x 2 airports
   python3 gen_searches.py --full     # FULL: every valid date pair (slow)
   ```
2. In Chrome: create a tab, then for each round-trip URL — `navigate`, then run
   `extract_options.js` via the javascript_tool.
3. For each result, find the cheapest option that meets ALL constraints:
   1 stop, no overnight layover (no "one day later" that implies an overnight
   wait), layover 2–6h, sane arrival. Note its price + times.
4. Append one line per run to `watchlog.md` (date, best COMPLIANT price + route +
   times, and the absolute-cheapest for trend).
5. Tell Steve: best compliant option today, and whether it beat previous days.
   **Flag loudly if a compliant round-trip drops under ~₪1,800 pp** — that's a
   real deal worth booking fast (self-transfers via Kiwi/MyTrip "Select" give a
   connection guarantee).

## Notes / gotchas

- **Date-bar "cheapest per day" prices LIE** — they're 14–23h overnight ordeals.
  Only trust the detailed "Flight option" blocks.
- Google Flights / `flights.py` does NOT show self-transfers — don't rely on it
  for this trip. Skyscanner-in-Chrome is the real engine.
- Skyscanner blocks plain HTTP (403) and its internal API tokens expire — must
  read the DOM in the live browser tab.
