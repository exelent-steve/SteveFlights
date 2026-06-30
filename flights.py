#!/usr/bin/env python3
"""SteveFlights — cheap TLV<->UK flight finder for the bein-hametzarim trip.

Searches Google Flights (via the free `fast-flights` library) for every
date / airport combination allowed by config.py, enforces the connection
and layover rules, then prints a ranked table of the cheapest round-trips
and saves a timestamped snapshot so you can spot price drops over time.

Strategy: each ONE-WAY leg is searched separately and cached, then legs are
combined into round-trips. This gives full layover control on BOTH directions
and accurate low-cost-carrier pricing. Trade-off: it can miss legacy-carrier
round-trip-only discounts (rare on this route).

Run:
    python3 flights.py                 # full search with config.py defaults
    python3 flights.py --top 15        # show more rows
    python3 flights.py --max-price 6000   # only show trips at/under this total
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

from fast_flights import FlightQuery, Passengers, create_query, get_flights

import config

RESULTS_DIR = Path(__file__).parent / "results"


# ─── Leg model ───────────────────────────────────────────────
@dataclass
class Leg:
    """One valid one-way option (a flight Google offered) after filtering."""

    direction: str          # "out" or "back"
    date: str               # YYYY-MM-DD of departure
    from_airport: str
    to_airport: str
    price_total: int        # for the whole party, in CURRENCY
    airlines: str
    stops: int
    depart: str             # "HH:MM"
    arrive_local: str       # "YYYY-MM-DD HH:MM" at final destination
    layover: str            # human description, "" for nonstop
    layover_ok: bool        # does every connection sit inside 2-6h?
    duration_min: int       # total travel time in minutes

    @property
    def duration_str(self) -> str:
        h, m = divmod(self.duration_min, 60)
        return f"{h}h{m:02d}m"


def _to_datetime(simple) -> dt.datetime | None:
    # Google sometimes returns a partial time ([16] means 16:00) or a glitched
    # one ([None, 25]). Pad missing minutes; bail out (None) if anything is None.
    date = list(simple.date)
    time = list(simple.time)
    if len(date) < 3 or any(x is None for x in date[:3]):
        return None
    h = time[0] if len(time) > 0 else 0
    mi = time[1] if len(time) > 1 else 0
    if h is None or mi is None:
        return None
    return dt.datetime(date[0], date[1], date[2], h, mi)


def _layover_ok_and_label(legs) -> tuple[bool, str]:
    """Describe every connection and whether it sits inside the 2-6h window.

    Always returns a human label (so the user can see WHY an option breaks the
    rule); `ok` is False if any layover is outside the window or unparseable.
    """
    ok = True
    labels = []
    for a, b in zip(legs, legs[1:]):
        arr, dep = _to_datetime(a.arrival), _to_datetime(b.departure)
        if arr is None or dep is None:
            return False, "?"
        gap = (dep - arr).total_seconds() / 3600
        if gap < config.MIN_LAYOVER_HOURS or gap > config.MAX_LAYOVER_HOURS:
            ok = False
        gh, gm = divmod(int(round(gap * 60)), 60)
        labels.append(f"{a.to_airport.code} {gh}h{gm:02d}m")
    return ok, " + ".join(labels)


def search_leg(direction: str, date: str, frm: str, to: str) -> list[Leg]:
    """Query one one-way leg and return the options passing all rules."""
    query = create_query(
        flights=[FlightQuery(date=date, from_airport=frm, to_airport=to,
                             max_stops=config.MAX_STOPS)],
        trip="one-way",
        seat="economy",
        passengers=Passengers(adults=config.ADULTS, children=config.CHILDREN),
        currency=config.CURRENCY,
        max_stops=config.MAX_STOPS,
    )
    try:
        results = get_flights(query)
    except Exception:
        # fast-flights raises when Google returns an empty result set, which
        # for this trip usually means "no <=1-stop options on this route/date".
        print(f"       (no ≤{config.MAX_STOPS}-stop options found)")
        return []

    out: list[Leg] = []
    for f in results:
        legs = f.flights
        if not legs:
            continue
        stops = len(legs) - 1
        if stops > config.MAX_STOPS:
            continue
        ok, layover_label = _layover_ok_and_label(legs) if stops else (True, "")
        first, last = legs[0], legs[-1]
        dep = _to_datetime(first.departure)
        arr = _to_datetime(last.arrival)
        out.append(Leg(
            direction=direction,
            date=date,
            from_airport=frm,
            to_airport=to,
            price_total=int(f.price),
            airlines=", ".join(f.airlines),
            stops=stops,
            depart=dep.strftime("%H:%M") if dep else "??:??",
            arrive_local=arr.strftime("%Y-%m-%d %H:%M") if arr else "?",
            layover=layover_label,
            layover_ok=ok,
            # true elapsed time (includes layovers); fall back to airtime sum
            duration_min=(int((arr - dep).total_seconds() // 60)
                          if dep and arr else sum(l.duration for l in legs)),
        ))
    out.sort(key=lambda l: l.price_total)
    return out


# ─── Trip building ───────────────────────────────────────────
@dataclass
class Trip:
    total: int
    per_person: int
    nights: int
    out_leg: Leg
    back_leg: Leg

    @property
    def layover_ok(self) -> bool:
        return self.out_leg.layover_ok and self.back_leg.layover_ok

    def route(self) -> str:
        return f"{config.ORIGIN}->{self.out_leg.to_airport} / {self.back_leg.from_airport}->{config.ORIGIN}"

    def key(self) -> tuple:
        return (self.out_leg.date, self.out_leg.to_airport, self.out_leg.price_total,
                self.back_leg.date, self.back_leg.from_airport, self.back_leg.price_total)


def _return_dates(out_date: str) -> list[str]:
    d0 = dt.date.fromisoformat(out_date)
    cap = dt.date.fromisoformat(config.MAX_RETURN_DATE)
    dates = []
    for n in range(config.MIN_NIGHTS, config.MAX_NIGHTS + 1):
        rd = d0 + dt.timedelta(days=n)
        if rd <= cap:
            dates.append(rd.isoformat())
    return dates


def run_search() -> list[Trip]:
    # Collect the unique legs we need so we never query the same one twice.
    out_needed = {(d, a) for d in config.OUT_DATES for a in config.DESTINATIONS}
    back_needed = {
        (rd, a)
        for d in config.OUT_DATES
        for rd in _return_dates(d)
        for a in config.DESTINATIONS
    }
    print(f"Searching {len(out_needed)} outbound + {len(back_needed)} return legs "
          f"({config.ADULTS} adults, {config.CURRENCY}, ≤{config.MAX_STOPS} stop)...\n")

    out_legs: dict[tuple[str, str], list[Leg]] = {}
    for date, airport in sorted(out_needed):
        print(f"  out  {config.ORIGIN}->{airport} {date}")
        out_legs[(date, airport)] = search_leg("out", date, config.ORIGIN, airport)
        time.sleep(config.REQUEST_DELAY_SECONDS)

    back_legs: dict[tuple[str, str], list[Leg]] = {}
    for date, airport in sorted(back_needed):
        print(f"  back {airport}->{config.ORIGIN} {date}")
        back_legs[(date, airport)] = search_leg("back", date, airport, config.ORIGIN)
        time.sleep(config.REQUEST_DELAY_SECONDS)

    def make_trip(out_leg: Leg, back_leg: Leg, nights: int) -> Trip:
        total = out_leg.price_total + back_leg.price_total
        return Trip(total=total, per_person=total // config.ADULTS,
                    nights=nights, out_leg=out_leg, back_leg=back_leg)

    # Combine. For each route/date pair build TWO candidates: the cheapest
    # overall, and the cheapest that respects the 2-6h layover rule. The user
    # can then weigh "cheaper but overnight" against "pricier but civilised".
    trips: dict[tuple, Trip] = {}
    for out_date in config.OUT_DATES:
        for out_airport in config.DESTINATIONS:
            outs = out_legs.get((out_date, out_airport)) or []
            if not outs:
                continue
            for ret_date in _return_dates(out_date):
                nights = (dt.date.fromisoformat(ret_date)
                          - dt.date.fromisoformat(out_date)).days
                for back_airport in config.DESTINATIONS:
                    backs = back_legs.get((ret_date, back_airport)) or []
                    if not backs:
                        continue
                    # cheapest overall (legs already sorted by price)
                    cand = [make_trip(outs[0], backs[0], nights)]
                    # cheapest fully rule-compliant, if such legs exist
                    ok_out = next((l for l in outs if l.layover_ok), None)
                    ok_back = next((l for l in backs if l.layover_ok), None)
                    if ok_out and ok_back:
                        cand.append(make_trip(ok_out, ok_back, nights))
                    for t in cand:
                        trips[t.key()] = t
    return sorted(trips.values(), key=lambda t: t.total)


# ─── Output ──────────────────────────────────────────────────
def print_table(trips: list[Trip], top: int, max_price: int | None) -> None:
    shown = [t for t in trips if max_price is None or t.total <= max_price][:top]
    if not shown:
        print("\nNo trips matched. Loosen the rules in config.py (layover, nights, price).")
        return

    cur = config.CURRENCY
    print(f"\n{'#':>2}  {'TOTAL':>8}  {'pp':>6}  {'nights':>6}  {'route':<17}  "
          f"{'out date':<10} {'back date':<10}  layover")
    print("─" * 118)
    for i, t in enumerate(shown, 1):
        flag = "✅ 2-6h" if t.layover_ok else "⚠️ breaks rule"
        if t.total <= config.PRICE_ALERT_TOTAL and t.layover_ok:
            flag += "  ✨ DEAL"
        print(f"{i:>2}  {t.total:>8,}  {t.per_person:>6,}  {t.nights:>6}  "
              f"{t.route():<17}  {t.out_leg.date:<10} {t.back_leg.date:<10}  {flag}")
        o, b = t.out_leg, t.back_leg
        print(f"      out : {o.depart} dep, {o.stops} stop, {o.duration_str:<7} "
              f"{o.airlines}{('  via ' + o.layover) if o.layover else '  (nonstop)'}")
        print(f"      back: {b.depart} dep, {b.stops} stop, {b.duration_str:<7} "
              f"{b.airlines}{('  via ' + b.layover) if b.layover else '  (nonstop)'}")
    print(f"\nPrices are TOTAL for {config.ADULTS} travellers, in {cur}. "
          f"'pp' = per person.  ⚠️ = a layover falls outside your 2-6h window.")


def save_snapshot(trips: list[Trip]) -> Path | None:
    if not trips:
        return None
    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    payload = {
        "checked_at": dt.datetime.now().isoformat(timespec="seconds"),
        "cheapest_total": trips[0].total,
        "cheapest_per_person": trips[0].per_person,
        "trips": [
            {**asdict(t), "out_leg": asdict(t.out_leg), "back_leg": asdict(t.back_leg)}
            for t in trips[:25]
        ],
    }
    path = RESULTS_DIR / f"{stamp}.json"
    path.write_text(json.dumps(payload, indent=2))

    # Compare with the previous snapshot to flag movement.
    prior = sorted(RESULTS_DIR.glob("20*.json"))
    if len(prior) >= 2:
        last = json.loads(prior[-2].read_text())
        delta = trips[0].total - last["cheapest_total"]
        if delta < 0:
            print(f"\n↓ Cheapest dropped {abs(delta):,} {config.CURRENCY} "
                  f"since {last['checked_at']} (was {last['cheapest_total']:,}).")
        elif delta > 0:
            print(f"\n↑ Cheapest rose {delta:,} {config.CURRENCY} "
                  f"since {last['checked_at']} (was {last['cheapest_total']:,}).")
        else:
            print(f"\n= Cheapest unchanged since {last['checked_at']}.")
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description="Find cheap TLV<->UK round-trips.")
    ap.add_argument("--top", type=int, default=10, help="rows to display")
    ap.add_argument("--max-price", type=int, default=None,
                    help="only show trips at/under this TOTAL price")
    args = ap.parse_args()

    trips = run_search()
    print_table(trips, top=args.top, max_price=args.max_price)
    path = save_snapshot(trips)
    if path:
        print(f"Snapshot saved: {path}")


if __name__ == "__main__":
    main()
