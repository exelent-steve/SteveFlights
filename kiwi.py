"""Kiwi.com (Tequila) API backend — finds self-transfer / virtual-interline routes.

This is what Skyscanner uses under the hood for 'self-transfer' options like
Blue Bird TLV→KGS + easyJet KGS→LPL. Google Flights never shows these.

API docs: https://tequila.kiwi.com/portal/docs/tequila-api/search_api
Free tier: sign up at tequila.kiwi.com to get a key.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import requests

import config

TEQUILA_URL = "https://api.tequila.kiwi.com/v2/search"
TIMEOUT = 20


@dataclass
class KiwiLeg:
    from_airport: str
    to_airport: str
    airlines: list[str]
    depart: str          # "YYYY-MM-DD HH:MM"
    arrive: str          # "YYYY-MM-DD HH:MM"
    duration_min: int
    is_self_transfer: bool


@dataclass
class KiwiTrip:
    total: int           # in CURRENCY, whole party
    per_person: int
    nights: int
    out_legs: list[KiwiLeg]
    back_legs: list[KiwiLeg]
    booking_token: str   # deep-link to kiwi.com booking page

    @property
    def out_dep(self) -> str:
        return self.out_legs[0].depart[:10] if self.out_legs else ""

    @property
    def back_dep(self) -> str:
        return self.back_legs[0].depart[:10] if self.back_legs else ""

    @property
    def out_airport(self) -> str:
        return self.out_legs[-1].to_airport if self.out_legs else ""

    @property
    def back_airport(self) -> str:
        return self.back_legs[0].from_airport if self.back_legs else ""

    @property
    def has_self_transfer(self) -> bool:
        return any(l.is_self_transfer for l in self.out_legs + self.back_legs)


def _parse_itinerary(item: dict, out_date: str, min_n: int, max_n: int) -> KiwiTrip | None:
    """Convert one Kiwi result item into a KiwiTrip, or None if it doesn't fit."""
    price = item.get("price")
    if price is None:
        return None
    total = int(round(float(price)))
    token = item.get("booking_token", "")

    # Kiwi returns the full outbound + inbound route as a flat list of segments.
    # Segments are tagged with their 'return' field: 0 = outbound, 1 = inbound.
    segments = item.get("route", [])
    if not segments:
        return None

    def parse_legs(segs: list[dict]) -> list[KiwiLeg]:
        legs = []
        for s in segs:
            dep_ts = s.get("dTime")
            arr_ts = s.get("aTime")
            if dep_ts is None or arr_ts is None:
                continue
            dep_dt = dt.datetime.utcfromtimestamp(dep_ts)
            arr_dt = dt.datetime.utcfromtimestamp(arr_ts)
            duration = int((arr_dt - dep_dt).total_seconds() // 60)
            legs.append(KiwiLeg(
                from_airport=s.get("flyFrom", "?"),
                to_airport=s.get("flyTo", "?"),
                airlines=[s.get("operating_carrier", s.get("airline", "?"))],
                depart=dep_dt.strftime("%Y-%m-%d %H:%M"),
                arrive=arr_dt.strftime("%Y-%m-%d %H:%M"),
                duration_min=duration,
                is_self_transfer=bool(s.get("guarantee", False)),
            ))
        return legs

    out_segs = [s for s in segments if s.get("return", 0) == 0]
    back_segs = [s for s in segments if s.get("return", 0) == 1]

    if not out_segs:
        return None

    out_legs = parse_legs(out_segs)
    back_legs = parse_legs(back_segs)

    # Compute nights only when we have both directions.
    nights = 0
    if out_legs and back_legs:
        out_d = dt.date.fromisoformat(out_legs[0].depart[:10])
        back_d = dt.date.fromisoformat(back_legs[0].depart[:10])
        nights = (back_d - out_d).days
        if nights < min_n or nights > max_n:
            return None

    return KiwiTrip(
        total=total,
        per_person=total // max(config.ADULTS + config.CHILDREN, 1),
        nights=nights,
        out_legs=out_legs,
        back_legs=back_legs,
        booking_token=token,
    )


def search_kiwi(api_key: str) -> list[KiwiTrip]:
    """Run the Kiwi search for all date combos in config and return sorted trips."""
    # Build a combined fly_to that covers both destination airports.
    fly_to = ",".join(config.DESTINATIONS)

    # Earliest and latest return we'll accept.
    out_dates = config.OUT_DATES
    if not out_dates:
        return []

    min_dep = min(out_dates)
    max_dep = max(out_dates)
    # Return window: min_nights after earliest outbound → latest allowed.
    min_ret = (dt.date.fromisoformat(min_dep)
               + dt.timedelta(days=config.MIN_NIGHTS)).isoformat()
    max_ret = config.MAX_RETURN_DATE

    params = {
        "fly_from": config.ORIGIN,
        "fly_to": fly_to,
        "date_from": dt.date.fromisoformat(min_dep).strftime("%d/%m/%Y"),
        "date_to":   dt.date.fromisoformat(max_dep).strftime("%d/%m/%Y"),
        "return_from": dt.date.fromisoformat(min_ret).strftime("%d/%m/%Y"),
        "return_to":   dt.date.fromisoformat(max_ret).strftime("%d/%m/%Y"),
        "nights_in_dst_from": config.MIN_NIGHTS,
        "nights_in_dst_to":   config.MAX_NIGHTS,
        "adults":   config.ADULTS,
        "children": config.CHILDREN,
        "max_stopovers": config.MAX_STOPS,
        "curr":   config.CURRENCY,
        "limit":  50,
        "sort":   "price",
        "flight_type": "round",
        "vehicle_type": "aircraft",
    }

    headers = {"apikey": api_key, "Accept": "application/json"}

    try:
        r = requests.get(TEQUILA_URL, params=params, headers=headers, timeout=TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  Kiwi API error: {e}")
        return []

    data = r.json()
    raw_trips = data.get("data", [])
    trips = []
    for item in raw_trips:
        t = _parse_itinerary(item, min_dep,
                             config.MIN_NIGHTS, config.MAX_NIGHTS)
        if t:
            trips.append(t)

    trips.sort(key=lambda t: t.total)
    return trips


def booking_url(token: str) -> str:
    """Direct link to book this itinerary on Kiwi.com."""
    adults = config.ADULTS
    children = config.CHILDREN
    return (f"https://www.kiwi.com/en/booking?token={token}"
            f"&adults={adults}&children={children}")
