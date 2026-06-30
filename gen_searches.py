#!/usr/bin/env python3
"""Generate the Skyscanner search URLs to check on a given morning.

Applies Steve's firm constraints so we only ever look at bookable, valid trips:
  - outbound no earlier than max(2026-07-26, tomorrow)
  - NO travel on Friday or Saturday (Shabbat risk)
  - stay 5-8 nights
  - return no later than 2026-08-12
  - Liverpool (LPL) preferred, Manchester (MAN) allowed, mixing fine

Prints round-trip URLs for pure-LPL and pure-MAN, plus one-way leg URLs so we
can spot mixed-airport combos (in LPL / out MAN). Skyscanner blocks non-browser
requests, so these are meant to be opened in Chrome via the browser tools.

Usage:
    python3 gen_searches.py                # uses today's date
    python3 gen_searches.py 2026-07-15     # pretend it's this date
"""

import datetime as dt
import sys

ORIGIN = "TLV"
AIRPORTS = ["lpl", "man"]            # lowercase for the URL path
EARLIEST_OUT = dt.date(2026, 7, 26)
LATEST_RETURN = dt.date(2026, 8, 12)
MIN_NIGHTS = 5
MAX_NIGHTS = 8
ADULTS = 2

# Weekday numbers to avoid as TRAVEL days: Fri=4, Sat=5 (Mon=0 .. Sun=6)
BLOCKED_WEEKDAYS = {4, 5}

BASE = "https://www.skyscanner.co.il/transport/flights"
COMMON = (f"adults={ADULTS}&adultsv2={ADULTS}&cabinclass=economy"
          f"&children=0&childrenv2=&infants=0&preferdirects=false"
          f"&outboundaltsenabled=false&inboundaltsenabled=false")


def valid_day(d: dt.date) -> bool:
    return d.weekday() not in BLOCKED_WEEKDAYS


def yymmdd(d: dt.date) -> str:
    return d.strftime("%Y%m%d")


def date_pairs(today: dt.date):
    """All (out, ret) pairs satisfying every constraint."""
    earliest_out = max(EARLIEST_OUT, today + dt.timedelta(days=1))
    pairs = []
    out = earliest_out
    # Outbound can be any valid day from earliest_out up to (latest_return - min_nights)
    last_out = LATEST_RETURN - dt.timedelta(days=MIN_NIGHTS)
    while out <= last_out:
        if valid_day(out):
            for n in range(MIN_NIGHTS, MAX_NIGHTS + 1):
                ret = out + dt.timedelta(days=n)
                if ret <= LATEST_RETURN and valid_day(ret):
                    pairs.append((out, ret, n))
        out += dt.timedelta(days=1)
    return pairs


def round_trip_url(airport: str, out: dt.date, ret: dt.date) -> str:
    return (f"{BASE}/{ORIGIN.lower()}/{airport}/{yymmdd(out)}/{yymmdd(ret)}/"
            f"?{COMMON}&rtn=1")


def one_way_url(frm: str, to: str, d: dt.date) -> str:
    return f"{BASE}/{frm}/{to}/{yymmdd(d)}/?{COMMON}&rtn=0"


def quick_pairs(pairs, n_outbound=3, nights=(6, 7)):
    """A focused watch list: first few outbound days x 6-7 night stays.

    Enough to detect a market shift each morning without loading 60 pages.
    When one of these drops, switch to --full to sweep every valid pair.
    """
    out_days = sorted({p[0] for p in pairs})[:n_outbound]
    chosen = [p for p in pairs if p[0] in out_days and p[2] in nights]
    return chosen or pairs[:6]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    full = "--full" in sys.argv

    today = (dt.date.fromisoformat(args[0]) if args else dt.date.today())
    pairs = date_pairs(today)

    if not pairs:
        print(f"No valid trips remain as of {today} — too late to fly within the window.")
        return

    if not full:
        pairs = quick_pairs(pairs)

    mode = "FULL" if full else "QUICK"
    print(f"# Flight check for {today}  [{mode}]  ({len(pairs)} date pairs)\n")

    # Unique outbound and return days (for one-way / mixed-airport scanning)
    out_days = sorted({p[0] for p in pairs})
    ret_days = sorted({p[1] for p in pairs})

    print("## Round-trip searches (open these, read 'Flight option' blocks)\n")
    for out, ret, n in pairs:
        for a in AIRPORTS:
            print(f"# {a.upper()}  {out:%a %d %b} -> {ret:%a %d %b}  ({n} nights)")
            print(round_trip_url(a, out, ret))
        print()

    print("## One-way legs (for mixed-airport combos: in LPL / out MAN, etc.)\n")
    print("# Outbound (TLV -> UK)")
    for d in out_days:
        for a in AIRPORTS:
            print(f"# {ORIGIN}->{a.upper()} {d:%a %d %b}: {one_way_url(ORIGIN.lower(), a, d)}")
    print("\n# Return (UK -> TLV)")
    for d in ret_days:
        for a in AIRPORTS:
            print(f"# {a.upper()}->{ORIGIN} {d:%a %d %b}: {one_way_url(a, ORIGIN.lower(), d)}")


if __name__ == "__main__":
    main()
