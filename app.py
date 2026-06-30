"""SteveFlights — Streamlit UI

Pages:
  1. Search — run a live search (calls flights.py logic directly)
  2. Results — browse saved snapshots, spot price trends
  3. Settings — edit config.py values and save

Run: streamlit run app.py
"""

import json
import subprocess
import sys
import datetime as dt
from pathlib import Path

import streamlit as st

# ─── page config ─────────────────────────────────────────────
st.set_page_config(
    page_title="SteveFlights ✈️",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = Path(__file__).parent
RESULTS_DIR = ROOT / "results"
CONFIG_PATH = ROOT / "config.py"

# ─── sidebar nav ─────────────────────────────────────────────
page = st.sidebar.radio("Navigate", ["🔍 Search", "📊 Results", "⚙️ Settings"],
                        label_visibility="collapsed")

# ─── helpers ─────────────────────────────────────────────────

def read_config() -> dict:
    """Parse config.py into a dict of values."""
    ns = {}
    exec(CONFIG_PATH.read_text(), ns)
    return {k: v for k, v in ns.items() if not k.startswith("_") and k == k.upper()}


def load_snapshots() -> list[dict]:
    if not RESULTS_DIR.exists():
        return []
    snaps = sorted(RESULTS_DIR.glob("20*.json"), reverse=True)
    results = []
    for p in snaps:
        try:
            results.append(json.loads(p.read_text()))
        except Exception:
            pass
    return results


def price_trend(snaps: list[dict]) -> list[tuple[str, int]]:
    return [
        (s["checked_at"][:16], s["cheapest_total"])
        for s in reversed(snaps)
        if "cheapest_total" in s
    ]


def fmt_nis(n: int) -> str:
    return f"₪{n:,}"


def layover_badge(ok: bool) -> str:
    return "✅ ok" if ok else "⚠️ long"


# ═══════════════════════════════════════════════════════════════
#  PAGE: SEARCH
# ═══════════════════════════════════════════════════════════════
if page == "🔍 Search":
    st.title("✈️ SteveFlights")
    st.caption("Cheapest TLV ⇄ Manchester / Liverpool — 3 Weeks 2026")

    cfg = read_config()

    col1, col2 = st.columns([2, 3])
    with col1:
        st.subheader("Trip summary")
        st.write(f"**Out:** {', '.join(cfg.get('OUT_DATES', []))}")
        st.write(f"**Stay:** {cfg.get('MIN_NIGHTS')}–{cfg.get('MAX_NIGHTS')} nights "
                 f"(latest return {cfg.get('MAX_RETURN_DATE')})")
        st.write(f"**Airports:** TLV → {' or '.join(cfg.get('DESTINATIONS', []))}")
        st.write(f"**Passengers:** {cfg.get('ADULTS')} adults, {cfg.get('CHILDREN')} children")
        st.write(f"**Max stops:** {cfg.get('MAX_STOPS')}")
        st.write(f"**Layover window:** {cfg.get('MIN_LAYOVER_HOURS')}–{cfg.get('MAX_LAYOVER_HOURS')} hrs")
        st.write(f"**Deal alert below:** {fmt_nis(cfg.get('PRICE_ALERT_TOTAL', 0))} total "
                 f"({fmt_nis(cfg.get('PRICE_ALERT_TOTAL', 0) // max(cfg.get('ADULTS', 1), 1))} pp)")

    with col2:
        snaps = load_snapshots()
        if snaps:
            last = snaps[0]
            st.subheader("Last check")
            st.metric(
                "Cheapest total (both travellers)",
                fmt_nis(last["cheapest_total"]),
                delta=(
                    fmt_nis(last["cheapest_total"] - snaps[1]["cheapest_total"])
                    if len(snaps) > 1 else None
                ),
                delta_color="inverse",
            )
            st.caption(f"Checked at {last['checked_at']}")
            trend = price_trend(snaps)
            if len(trend) > 1:
                import pandas as pd
                df = pd.DataFrame(trend, columns=["time", "price"])
                st.line_chart(df.set_index("time"), height=160)

    st.divider()
    st.subheader("Run a new search")
    st.caption("This calls Google Flights live — takes ~30s for all date/airport combos.")

    if st.button("🔍 Search now", type="primary", use_container_width=True):
        placeholder = st.empty()
        with placeholder.container():
            st.info("Searching… (this takes ~30 seconds)")
        with st.spinner("Querying Google Flights…"):
            result = subprocess.run(
                [sys.executable, str(ROOT / "flights.py"), "--top", "20"],
                capture_output=True, text=True, cwd=str(ROOT),
            )
        placeholder.empty()
        if result.returncode == 0:
            st.success("Done! Switch to the **Results** tab to see the table.")
            st.text(result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout)
        else:
            st.error("Search failed:")
            st.code(result.stderr or result.stdout)


# ═══════════════════════════════════════════════════════════════
#  PAGE: RESULTS
# ═══════════════════════════════════════════════════════════════
elif page == "📊 Results":
    st.title("📊 Search Results")

    snaps = load_snapshots()
    if not snaps:
        st.info("No results yet — run a search first.")
        st.stop()

    # snapshot picker
    labels = [s["checked_at"] for s in snaps]
    chosen_label = st.selectbox("Snapshot", labels)
    snap = snaps[labels.index(chosen_label)]

    trips = snap.get("trips", [])
    if not trips:
        st.warning("No trips in this snapshot.")
        st.stop()

    st.caption(
        f"Cheapest total: **{fmt_nis(snap['cheapest_total'])}** "
        f"({fmt_nis(snap['cheapest_per_person'])} pp)"
    )

    # optional filter
    with st.expander("Filter options"):
        max_price = st.slider(
            "Max total price (₪)",
            min_value=0, max_value=20000,
            value=min(20000, trips[-1]["total"]),
            step=250,
        )
        only_ok = st.checkbox("Only show trips where BOTH legs have 2–6h layover")

    # render trips
    cfg = read_config()
    alert_threshold = cfg.get("PRICE_ALERT_TOTAL", 0)

    shown = 0
    for t in trips:
        if t["total"] > max_price:
            continue
        o = t["out_leg"]
        b = t["back_leg"]
        out_ok = o.get("layover_ok", True)
        back_ok = b.get("layover_ok", True)
        trip_ok = out_ok and back_ok
        if only_ok and not trip_ok:
            continue

        is_deal = t["total"] <= alert_threshold and trip_ok
        bg = "rgba(255,215,0,0.12)" if is_deal else "rgba(255,77,77,0.06)" if not trip_ok else ""
        label = "✨ DEAL" if is_deal else ("⚠️ long layover" if not trip_ok else "")

        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2, 2, 1, 2])
            with c1:
                st.markdown(f"### {fmt_nis(t['total'])}")
                st.caption(f"{fmt_nis(t['per_person'])} pp · {t['nights']} nights")
            with c2:
                st.markdown(f"**{o['from_airport']} → {o['to_airport']}**  "
                            f"{o['date']}  {o['depart']}")
                st.markdown(f"**{b['from_airport']} → {b['to_airport']}**  "
                            f"{b['date']}  {b['depart']}")
            with c3:
                st.markdown(f"{'✅' if out_ok else '⚠️'} out")
                st.markdown(f"{'✅' if back_ok else '⚠️'} back")
            with c4:
                if label:
                    st.markdown(f"**{label}**")
                st.caption(
                    f"Out: {o['airlines']}  "
                    f"{('via ' + o['layover']) if o.get('layover') else 'nonstop'}"
                )
                st.caption(
                    f"Back: {b['airlines']}  "
                    f"{('via ' + b['layover']) if b.get('layover') else 'nonstop'}"
                )
        shown += 1

    if shown == 0:
        st.info("No trips match the current filter.")

    # price history chart
    all_snaps = load_snapshots()
    trend = price_trend(all_snaps)
    if len(trend) > 1:
        st.divider()
        st.subheader("Price history")
        import pandas as pd
        df = pd.DataFrame(trend, columns=["time", "₪ total"])
        st.line_chart(df.set_index("time"), height=220)


# ═══════════════════════════════════════════════════════════════
#  PAGE: SETTINGS
# ═══════════════════════════════════════════════════════════════
elif page == "⚙️ Settings":
    st.title("⚙️ Settings")
    st.caption("Changes here rewrite `config.py` — take effect on the next search.")

    cfg = read_config()

    with st.form("settings_form"):
        st.subheader("Airports")
        destinations = st.multiselect(
            "UK airports to try",
            ["MAN", "LPL", "LHR", "STN", "LGW", "BHX"],
            default=cfg.get("DESTINATIONS", ["MAN", "LPL"]),
        )

        st.subheader("Dates")
        raw_out = st.text_input(
            "Outbound dates (YYYY-MM-DD, comma-separated)",
            value=", ".join(cfg.get("OUT_DATES", ["2026-07-26"])),
        )
        c1, c2 = st.columns(2)
        min_nights = c1.number_input("Min nights", 1, 30, int(cfg.get("MIN_NIGHTS", 5)))
        max_nights = c2.number_input("Max nights", 1, 30, int(cfg.get("MAX_NIGHTS", 7)))
        max_return = st.text_input(
            "Hard latest return date (YYYY-MM-DD)",
            value=cfg.get("MAX_RETURN_DATE", "2026-08-12"),
        )

        st.subheader("Passengers")
        c1, c2 = st.columns(2)
        adults = c1.number_input("Adults (16+ books as adult)", 1, 9, int(cfg.get("ADULTS", 2)))
        children = c2.number_input("Children", 0, 9, int(cfg.get("CHILDREN", 0)))

        st.subheader("Connection rules")
        max_stops = st.number_input("Max stops", 0, 2, int(cfg.get("MAX_STOPS", 1)))
        c1, c2 = st.columns(2)
        min_layover = c1.number_input(
            "Min layover (hours)", 0.5, 6.0, float(cfg.get("MIN_LAYOVER_HOURS", 2.0)), step=0.5
        )
        max_layover = c2.number_input(
            "Max layover (hours)", 1.0, 24.0, float(cfg.get("MAX_LAYOVER_HOURS", 6.0)), step=0.5
        )

        st.subheader("Pricing")
        currency = st.selectbox("Currency", ["ILS", "GBP", "EUR", "USD"],
                                index=["ILS", "GBP", "EUR", "USD"].index(
                                    cfg.get("CURRENCY", "ILS")))
        alert = st.number_input(
            "Flag as ✨ DEAL if total ≤ this amount",
            min_value=0, max_value=100000,
            value=int(cfg.get("PRICE_ALERT_TOTAL", 6400)),
            step=100,
        )
        delay = st.number_input(
            "Delay between queries (seconds)",
            min_value=0.5, max_value=10.0,
            value=float(cfg.get("REQUEST_DELAY_SECONDS", 1.5)),
            step=0.5,
        )

        submitted = st.form_submit_button("💾 Save settings", type="primary")

    if submitted:
        out_dates = [d.strip() for d in raw_out.split(",") if d.strip()]
        new_cfg = f'''# ─── Trip configuration ──────────────────────────────────────
# Edit this file to change what the flight finder searches for.
# All prices come back in the currency below (ILS = Israeli Shekel).

ORIGIN = "TLV"                      # always fly out of / back to Tel Aviv

# UK airports to consider, at EITHER end of the trip (mix and match allowed).
# LPL = Liverpool (usually cheaper), MAN = Manchester (more flights).
DESTINATIONS = {destinations!r}

# Outbound dates to try (Israel -> UK). Add a day either side for flexibility.
OUT_DATES = {out_dates!r}

# How long to stay, in nights. We build return dates from each outbound date.
MIN_NIGHTS = {int(min_nights)}
MAX_NIGHTS = {int(max_nights)}

# Hard limit: never return later than this (inclusive).
MAX_RETURN_DATE = "{max_return}"

# Passengers
ADULTS = {int(adults)}                          # 16+ books as an adult
CHILDREN = {int(children)}

# Connection rules
MAX_STOPS = {int(max_stops)}                    # 0 (nonstop) or 1 connection only
MIN_LAYOVER_HOURS = {float(min_layover)}        # need time to clear/recheck
MAX_LAYOVER_HOURS = {float(max_layover)}        # don\'t want longer than this

# Money
CURRENCY = "{currency}"
# Flag any round-trip at or below this TOTAL price for the whole party.
PRICE_ALERT_TOTAL = {int(alert)}

# Politeness: seconds to wait between Google Flights queries.
REQUEST_DELAY_SECONDS = {float(delay)}
'''
        CONFIG_PATH.write_text(new_cfg)
        st.success("Settings saved! Run a new search to see the effect.")
