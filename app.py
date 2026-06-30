"""SteveFlights — Streamlit UI

Pages:
  1. Search — run a live search (Google Flights + Kiwi self-transfers)
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

ROOT = Path(__file__).parent
RESULTS_DIR = ROOT / "results"
CONFIG_PATH = ROOT / "config.py"

st.set_page_config(
    page_title="SteveFlights ✈️",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

page = st.sidebar.radio("Navigate", ["🔍 Search", "📊 Results", "⚙️ Settings"],
                        label_visibility="collapsed")

# ─── helpers ─────────────────────────────────────────────────

def read_config() -> dict:
    ns = {}
    exec(CONFIG_PATH.read_text(), ns)
    return {k: v for k, v in ns.items() if not k.startswith("_") and k == k.upper()}


def load_snapshots() -> list[dict]:
    if not RESULTS_DIR.exists():
        return []
    return [
        json.loads(p.read_text())
        for p in sorted(RESULTS_DIR.glob("20*.json"), reverse=True)
        if p.stat().st_size > 10
    ]


def price_trend(snaps: list[dict]) -> list[tuple[str, int]]:
    return [(s["checked_at"][:16], s["cheapest_total"])
            for s in reversed(snaps) if "cheapest_total" in s]


def fmt_nis(n: int) -> str:
    return f"₪{n:,}"


# ═══════════════════════════════════════════════════════════════
#  PAGE: SEARCH
# ═══════════════════════════════════════════════════════════════
if page == "🔍 Search":
    st.title("✈️ SteveFlights")
    st.caption("TLV ⇄ Manchester / Liverpool · 3 Weeks 2026")

    cfg = read_config()
    has_kiwi = bool(cfg.get("KIWI_API_KEY", "").strip())

    # ── trip summary ──────────────────────────────────────────
    col1, col2 = st.columns([2, 3])
    with col1:
        st.subheader("Trip")
        st.write(f"**Out:** {', '.join(cfg.get('OUT_DATES', []))}")
        st.write(f"**Stay:** {cfg.get('MIN_NIGHTS')}–{cfg.get('MAX_NIGHTS')} nights "
                 f"(latest back {cfg.get('MAX_RETURN_DATE')})")
        st.write(f"**To/from:** {' or '.join(cfg.get('DESTINATIONS', []))}")
        st.write(f"**Pax:** {cfg.get('ADULTS')} adults, {cfg.get('CHILDREN')} children")
        st.write(f"**Max stops:** {cfg.get('MAX_STOPS')}")
        st.write(f"**Layover:** {cfg.get('MIN_LAYOVER_HOURS')}–{cfg.get('MAX_LAYOVER_HOURS')} hrs")
        pp = cfg.get("PRICE_ALERT_TOTAL", 0) // max(cfg.get("ADULTS", 1), 1)
        st.write(f"**Deal alert:** ≤ {fmt_nis(cfg.get('PRICE_ALERT_TOTAL', 0))} total "
                 f"({fmt_nis(pp)} pp)")

    with col2:
        snaps = load_snapshots()
        if snaps:
            last = snaps[0]
            st.subheader("Last check")
            delta = (last["cheapest_total"] - snaps[1]["cheapest_total"]
                     if len(snaps) > 1 else None)
            st.metric("Cheapest (both travellers)", fmt_nis(last["cheapest_total"]),
                      delta=f"{delta:+,} ₪" if delta is not None else None,
                      delta_color="inverse")
            st.caption(f"Checked at {last['checked_at']}")
            trend = price_trend(snaps)
            if len(trend) > 1:
                import pandas as pd
                df = pd.DataFrame(trend, columns=["time", "price"])
                st.line_chart(df.set_index("time"), height=160)

    st.divider()

    # ── Kiwi setup banner ─────────────────────────────────────
    if not has_kiwi:
        st.warning(
            "**⚠️ Self-transfer flights (like Blue Bird + easyJet to Liverpool) are NOT "
            "searchable without a Kiwi.com API key.** These are often the cheapest options "
            "and Skyscanner finds them exactly because it uses Kiwi under the hood.\n\n"
            "👉 **Get a free key** (2 min): [tequila.kiwi.com](https://tequila.kiwi.com/portal/login) "
            "→ Sign up → API Keys → copy key → paste in ⚙️ Settings → Kiwi API Key."
        )

    # ── search buttons ────────────────────────────────────────
    c1, c2 = st.columns(2)
    run_google = c1.button("🔍 Google Flights search",
                           type="primary", use_container_width=True,
                           help="Single-ticket itineraries only. Free, no key needed.")
    run_kiwi = c2.button("🔀 Kiwi self-transfer search",
                         type="primary" if has_kiwi else "secondary",
                         use_container_width=True,
                         disabled=not has_kiwi,
                         help="Virtual interlines (Blue Bird→easyJet etc). Requires Kiwi API key.")

    if run_google:
        with st.spinner("Querying Google Flights (~30s)…"):
            result = subprocess.run(
                [sys.executable, str(ROOT / "flights.py"), "--top", "20"],
                capture_output=True, text=True, cwd=str(ROOT),
            )
        if result.returncode == 0:
            st.success("Done — results saved. Check **📊 Results** tab.")
            with st.expander("Raw output"):
                st.text(result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout)
        else:
            st.error("Search failed")
            st.code(result.stderr or result.stdout)

    if run_kiwi and has_kiwi:
        with st.spinner("Querying Kiwi.com (self-transfers)…"):
            try:
                import importlib, config as cfg_mod
                importlib.reload(cfg_mod)
                from kiwi import search_kiwi, booking_url
                trips = search_kiwi(cfg_mod.KIWI_API_KEY)
            except Exception as e:
                trips = []
                st.error(f"Kiwi search error: {e}")

        if not trips:
            st.info("No Kiwi results — either no flights found or check your API key in Settings.")
        else:
            alert = cfg.get("PRICE_ALERT_TOTAL", 99999)
            st.success(f"Found {len(trips)} Kiwi options. Cheapest: {fmt_nis(trips[0].total)}")

            # Save Kiwi snapshot alongside Google ones.
            RESULTS_DIR.mkdir(exist_ok=True)
            stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
            kiwi_path = RESULTS_DIR / f"{stamp}-kiwi.json"
            kiwi_path.write_text(json.dumps({
                "source": "kiwi",
                "checked_at": dt.datetime.now().isoformat(timespec="seconds"),
                "cheapest_total": trips[0].total,
                "cheapest_per_person": trips[0].per_person,
                "trips": [
                    {
                        "total": t.total, "per_person": t.per_person, "nights": t.nights,
                        "has_self_transfer": t.has_self_transfer,
                        "out_dep": t.out_dep, "back_dep": t.back_dep,
                        "out_airport": t.out_airport, "back_airport": t.back_airport,
                        "out_legs": [{"from": l.from_airport, "to": l.to_airport,
                                      "airlines": l.airlines, "depart": l.depart,
                                      "arrive": l.arrive,
                                      "self_transfer": l.is_self_transfer} for l in t.out_legs],
                        "back_legs": [{"from": l.from_airport, "to": l.to_airport,
                                       "airlines": l.airlines, "depart": l.depart,
                                       "arrive": l.arrive,
                                       "self_transfer": l.is_self_transfer} for l in t.back_legs],
                        "booking_url": booking_url(t.booking_token),
                    }
                    for t in trips[:30]
                ],
            }, indent=2))

            for t in trips[:12]:
                is_deal = t.total <= alert
                badge = "✨ DEAL " if is_deal else ""
                self_tx = "🔀 self-transfer" if t.has_self_transfer else "🎫 single ticket"
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 4, 2])
                    with c1:
                        st.markdown(f"### {badge}{fmt_nis(t.total)}")
                        st.caption(f"{fmt_nis(t.per_person)} pp · {t.nights} nights")
                        st.caption(self_tx)
                    with c2:
                        st.markdown("**Outbound**")
                        for l in t.out_legs:
                            pfx = "🔀 " if l.is_self_transfer else "✈️ "
                            st.caption(f"{pfx}{l.from_airport}→{l.to_airport}  "
                                       f"{l.depart[11:16]}→{l.arrive[11:16]}  "
                                       f"{', '.join(l.airlines)}")
                        st.markdown("**Return**")
                        for l in t.back_legs:
                            pfx = "🔀 " if l.is_self_transfer else "✈️ "
                            st.caption(f"{pfx}{l.from_airport}→{l.to_airport}  "
                                       f"{l.depart[11:16]}→{l.arrive[11:16]}  "
                                       f"{', '.join(l.airlines)}")
                    with c3:
                        url = booking_url(t.booking_token)
                        st.link_button("Book on Kiwi →", url, use_container_width=True)


# ═══════════════════════════════════════════════════════════════
#  PAGE: RESULTS
# ═══════════════════════════════════════════════════════════════
elif page == "📊 Results":
    st.title("📊 Results")

    snaps = load_snapshots()
    if not snaps:
        st.info("No results yet — run a search first.")
        st.stop()

    # split Google vs Kiwi snapshots
    google_snaps = [s for s in snaps if s.get("source") != "kiwi"]
    kiwi_snaps = [s for s in snaps if s.get("source") == "kiwi"]

    tab1, tab2 = st.tabs(["Google Flights", "Kiwi (self-transfers)"])

    # ── Google tab ────────────────────────────────────────────
    with tab1:
        if not google_snaps:
            st.info("No Google Flights results yet.")
        else:
            labels = [s["checked_at"] for s in google_snaps]
            chosen = st.selectbox("Snapshot", labels, key="g_snap")
            snap = google_snaps[labels.index(chosen)]
            trips = snap.get("trips", [])

            st.caption(f"Cheapest: **{fmt_nis(snap['cheapest_total'])}** "
                       f"({fmt_nis(snap['cheapest_per_person'])} pp)")

            cfg = read_config()
            alert = cfg.get("PRICE_ALERT_TOTAL", 0)

            with st.expander("Filter"):
                max_price = st.slider("Max total (₪)", 0, 30000,
                                      min(30000, max(t["total"] for t in trips)),
                                      step=250, key="g_price")
                only_ok = st.checkbox("Only 2–6h layovers on both legs", key="g_ok")

            shown = 0
            for t in trips:
                if t["total"] > max_price:
                    continue
                o, b = t["out_leg"], t["back_leg"]
                out_ok = o.get("layover_ok", True)
                back_ok = b.get("layover_ok", True)
                if only_ok and not (out_ok and back_ok):
                    continue
                trip_ok = out_ok and back_ok
                is_deal = t["total"] <= alert and trip_ok
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([2, 2, 1, 2])
                    with c1:
                        st.markdown(f"### {fmt_nis(t['total'])}")
                        st.caption(f"{fmt_nis(t['per_person'])} pp · {t['nights']} nights")
                    with c2:
                        st.markdown(f"**TLV → {o['to_airport']}**  {o['date']}  {o['depart']}")
                        st.markdown(f"**{b['from_airport']} → TLV**  {b['date']}  {b['depart']}")
                    with c3:
                        st.write("✅" if out_ok else "⚠️", "out")
                        st.write("✅" if back_ok else "⚠️", "back")
                    with c4:
                        if is_deal:
                            st.markdown("**✨ DEAL**")
                        st.caption(f"Out: {o['airlines']}  "
                                   f"{('via ' + o['layover']) if o.get('layover') else 'nonstop'}")
                        st.caption(f"Back: {b['airlines']}  "
                                   f"{('via ' + b['layover']) if b.get('layover') else 'nonstop'}")
                shown += 1

            if shown == 0:
                st.info("No trips match the current filter.")

            # price history
            trend = price_trend(google_snaps)
            if len(trend) > 1:
                st.divider()
                st.subheader("Price history")
                import pandas as pd
                df = pd.DataFrame(trend, columns=["time", "₪ total"])
                st.line_chart(df.set_index("time"), height=200)

    # ── Kiwi tab ─────────────────────────────────────────────
    with tab2:
        if not kiwi_snaps:
            st.info("No Kiwi results yet. Add your API key in Settings, then search.")
        else:
            labels = [s["checked_at"] for s in kiwi_snaps]
            chosen = st.selectbox("Snapshot", labels, key="k_snap")
            snap = kiwi_snaps[labels.index(chosen)]
            trips = snap.get("trips", [])

            st.caption(f"Cheapest: **{fmt_nis(snap['cheapest_total'])}** "
                       f"({fmt_nis(snap['cheapest_per_person'])} pp)")

            cfg = read_config()
            alert = cfg.get("PRICE_ALERT_TOTAL", 0)

            with st.expander("Filter"):
                max_price = st.slider("Max total (₪)", 0, 30000,
                                      min(30000, max(t["total"] for t in trips)),
                                      step=250, key="k_price")
                only_self = st.checkbox("Only show self-transfer itineraries", key="k_self")

            from kiwi import booking_url
            for t in trips:
                if t["total"] > max_price:
                    continue
                if only_self and not t.get("has_self_transfer"):
                    continue
                is_deal = t["total"] <= alert
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 4, 2])
                    with c1:
                        st.markdown(f"### {fmt_nis(t['total'])}")
                        st.caption(f"{fmt_nis(t['per_person'])} pp · {t['nights']} nights")
                        if t.get("has_self_transfer"):
                            st.caption("🔀 self-transfer")
                        if is_deal:
                            st.markdown("**✨ DEAL**")
                    with c2:
                        st.markdown("**Outbound**")
                        for l in t.get("out_legs", []):
                            pfx = "🔀 " if l.get("self_transfer") else "✈️ "
                            st.caption(f"{pfx}{l['from']}→{l['to']}  "
                                       f"{l['depart'][11:16]}  "
                                       f"{', '.join(l['airlines'])}")
                        st.markdown("**Return**")
                        for l in t.get("back_legs", []):
                            pfx = "🔀 " if l.get("self_transfer") else "✈️ "
                            st.caption(f"{pfx}{l['from']}→{l['to']}  "
                                       f"{l['depart'][11:16]}  "
                                       f"{', '.join(l['airlines'])}")
                    with c3:
                        st.link_button("Book on Kiwi →",
                                       t.get("booking_url", "https://kiwi.com"),
                                       use_container_width=True)


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
            "Min layover (hours)", 0.5, 12.0, float(cfg.get("MIN_LAYOVER_HOURS", 2.0)), step=0.5
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
            min_value=0, max_value=200000, value=int(cfg.get("PRICE_ALERT_TOTAL", 6400)), step=100,
        )
        delay = st.number_input(
            "Delay between Google queries (seconds)",
            min_value=0.5, max_value=10.0,
            value=float(cfg.get("REQUEST_DELAY_SECONDS", 1.5)), step=0.5,
        )

        st.subheader("Kiwi.com API (for self-transfer flights)")
        st.caption(
            "Get a free key at [tequila.kiwi.com](https://tequila.kiwi.com/portal/login). "
            "Without this, Liverpool self-transfer routes (Blue Bird + easyJet) won't be found."
        )
        kiwi_key = st.text_input(
            "Kiwi API key", value=cfg.get("KIWI_API_KEY", ""),
            type="password", placeholder="paste key here",
        )

        submitted = st.form_submit_button("💾 Save settings", type="primary")

    if submitted:
        out_dates = [d.strip() for d in raw_out.split(",") if d.strip()]
        new_cfg = f'''# ─── Trip configuration ──────────────────────────────────────
ORIGIN = "TLV"

DESTINATIONS = {destinations!r}

OUT_DATES = {out_dates!r}

MIN_NIGHTS = {int(min_nights)}
MAX_NIGHTS = {int(max_nights)}

MAX_RETURN_DATE = "{max_return}"

ADULTS = {int(adults)}
CHILDREN = {int(children)}

MAX_STOPS = {int(max_stops)}
MIN_LAYOVER_HOURS = {float(min_layover)}
MAX_LAYOVER_HOURS = {float(max_layover)}

CURRENCY = "{currency}"
PRICE_ALERT_TOTAL = {int(alert)}

REQUEST_DELAY_SECONDS = {float(delay)}

# ─── Kiwi.com (Tequila) API ──────────────────────────────────
# Get a free key at: https://tequila.kiwi.com/portal/login
KIWI_API_KEY = {kiwi_key!r}
'''
        CONFIG_PATH.write_text(new_cfg)
        st.success("Saved! Run a new search from the Search page.")
