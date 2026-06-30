# ─── Trip configuration ──────────────────────────────────────
# Edit this file to change what the flight finder searches for.
# All prices come back in the currency below (ILS = Israeli Shekel).

ORIGIN = "TLV"                      # always fly out of / back to Tel Aviv

# UK airports to consider, at EITHER end of the trip (mix and match allowed).
# LPL = Liverpool (usually cheaper), MAN = Manchester (more flights).
DESTINATIONS = ["MAN", "LPL"]

# Outbound dates to try (Israel -> UK). Add a day either side for flexibility.
OUT_DATES = ["2026-07-26"]

# How long to stay, in nights. We build return dates from each outbound date.
MIN_NIGHTS = 5
MAX_NIGHTS = 7

# Hard limit: never return later than this (inclusive).
MAX_RETURN_DATE = "2026-08-12"

# Passengers
ADULTS = 2                          # you + the 16-year-old (16 books as an adult)
CHILDREN = 0

# Connection rules
MAX_STOPS = 1                       # 0 (nonstop) or 1 connection only
MIN_LAYOVER_HOURS = 2.0             # need time to clear/recheck for the next flight
MAX_LAYOVER_HOURS = 6.0             # don't want to sit in an airport longer than this

# Money
CURRENCY = "ILS"
# Flag any round-trip at or below this TOTAL price for the whole party (NIS).
# Set to your dream number; the finder highlights anything that beats it.
PRICE_ALERT_TOTAL = 6400            # = 3200 pp round-trip; lower it to chase harder

# Politeness: seconds to wait between Google Flights queries.
REQUEST_DELAY_SECONDS = 1.5

# ─── Kiwi.com (Tequila) API ──────────────────────────────────
# Get a free key at: https://tequila.kiwi.com/portal/login
# This is the ONLY way to find self-transfer flights (Blue Bird + easyJet etc).
# Leave empty ("") to skip Kiwi search and use Google Flights only.
KIWI_API_KEY = ""
