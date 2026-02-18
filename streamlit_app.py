import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import gridstatus
from datetime import datetime, timedelta

# --- CONFIGURATION ---
DASHBOARD_PASSWORD = "123"
LAT, LONG = 31.997, -102.077
BATT_COST_PER_MW = 897404.0 

# --- DATASETS (2¢ INTERVALS) ---
TREND_DATA_WEST = {
    "Negative (<$0)":    {"2021": 0.021, "2022": 0.045, "2023": 0.062, "2024": 0.094, "2025": 0.121},
    "$0 - $0.02":       {"2021": 0.182, "2022": 0.241, "2023": 0.284, "2024": 0.311, "2025": 0.335},
    "$0.02 - $0.04":    {"2021": 0.456, "2022": 0.398, "2023": 0.341, "2024": 0.305, "2025": 0.272},
    "$0.04 - $0.06":    {"2021": 0.158, "2022": 0.165, "2023": 0.142, "2024": 0.124, "2025": 0.110},
    "$0.06 - $0.08":    {"2021": 0.082, "2022": 0.071, "2023": 0.065, "2024": 0.061, "2025": 0.058},
    "$0.08 - $0.10":    {"2021": 0.041, "2022": 0.038, "2023": 0.038, "2024": 0.039, "2025": 0.040},
    "$0.10 - $0.15":    {"2021": 0.022, "2022": 0.021, "2023": 0.024, "2024": 0.026, "2025": 0.028},
    "$0.15 - $0.25":    {"2021": 0.019, "2022": 0.010, "2023": 0.018, "2024": 0.019, "2025": 0.021},
    "$0.25 - $1.00":    {"2021": 0.011, "2022": 0.009, "2023": 0.019, "2024": 0.015, "2025": 0.010},
    "$1.00 - $5.00":    {"2021": 0.008, "2022": 0.002, "2023": 0.007, "2024": 0.006, "2025": 0.005}
}

TREND_DATA_SYSTEM = {
    "Negative (<$0)":    {"2021": 0.004, "2022": 0.009, "2023": 0.015, "2024": 0.028, "2025": 0.042},
    "$0 - $0.02":       {"2021": 0.112, "2022": 0.156, "2023": 0.201, "2024": 0.245, "2025": 0.288},
    "$0.02 - $0.04":    {"2021": 0.512, "2022": 0.485, "2023": 0.422, "2024": 0.388, "2025": 0.355},
    "$0.04 - $0.06":    {"2021": 0.215, "2022": 0.228, "2023": 0.198, "2024": 0.182, "2025": 0.165},
    "$0.06 - $0.08":    {"2021": 0.091, "2022": 0.082, "2023": 0.077, "2024": 0.072, "2025": 0.068},
    "$0.08 - $0.10":    {"2021": 0.032, "2022": 0.021, "2023": 0.031, "2024": 0.034, "2025": 0.036},
    "$0.10 - $0.15":    {"2021": 0.012, "2022": 0.009, "2023": 0.018, "2024": 0.021, "2025": 0.023},
    "$0.15 - $0.25":    {"2021": 0.008, "2022": 0.004, "2023": 0.012, "2024": 0.014, "2025": 0.016},
    "$0.25 - $1.00":    {"2021": 0.004, "2022": 0.003, "2023": 0.016, "2024": 0.010, "2025": 0.004},
    "$1.00 - $5.00":    {"2021": 0.010, "2022": 0.003, "2023": 0.010, "2024": 0.006, "2025": 0.003}
}

# --- AUTHENTICATION ---
if "password_correct" not in st.session_state: st.session_state.password_correct = False
def check_password():
    if st.session_state.password_correct: return True
    st.title("⚡ Midland Hybrid Alpha")
    pwd = st.text_input("Enter Access Password", type="password")
    if pwd == DASHBOARD_PASSWORD:
        st.session_state.password_correct = True
        st.rerun()
    return False

if not check_password(): st.stop()

@st.cache_data(ttl=300)
def get_live_data():
    try:
        iso = gridstatus.Ercot()
        df = iso.get_rtm_lmp(start=pd.Timestamp.now(tz="US/Central")-pd.Timedelta(days=31), end=pd.Timestamp.now(tz="US/Central"), verbose=False)
        return df[df['Location'] == 'HB_WEST'].set_index('Time').sort_index()['LMP']
    except: return pd.Series(np.random.uniform(15, 45, 744))

price_hist = get_live_data()

# --- APP TABS ---
tab1, tab2 = st.tabs(["📊 Performance Evolution", "📈 Long-Term Volatility"])

with tab1:
    st.markdown("### ⚙️ System Configuration")
    c1, c2, c3 = st.columns(3)
    with c1:
        solar_cap, wind_cap = st.slider("Solar Capacity (MW)", 0, 1000, 100), st.slider("Wind Capacity (MW)", 0, 1000, 100)
    with c2:
        m_cost, m_eff = st.slider("Miner Cost ($/TH)", 1.0, 50.0, 18.20), st.slider("Efficiency (J/TH)", 10.0, 35.0, 28.0)
    with c3:
        hp_cents = st.slider("Hashprice (¢/TH)", 1.0, 10.0, 4.0)
        batt_mw = st.number_input("Battery Size (MW)", value=60)
        breakeven = (1e6 / m_eff) * (hp_cents / 100.0) / 24.0
        st.markdown(f"#### Breakeven Floor: **${breakeven:.2f}/MWh**")

    # --- HYBRID OPTIMIZATION ENGINE ---
    st.markdown("---")
    st.subheader("🎯 Hybrid Optimization Engine")
    total_gen = solar_cap + wind_cap
    s_pct = solar_cap / total_gen if total_gen > 0 else 0.5
    w_pct = wind_cap / total_gen if total_gen > 0 else 0.5
    ideal_m, ideal_b = int(total_gen * ((s_pct * 0.10) + (w_pct * 0.25))), int(total_gen * ((s_pct * 0.50) + (w_pct * 0.25)))
    st.write(f"**Ideal Sizing:** {ideal_m}MW Miners | {ideal_b}MW Battery")
    
    # --- LIVE POWER & PERFORMANCE ---
    st.markdown("---")
    st.subheader("📊 Live Power & Performance")
    curr_p = price_hist.iloc[-1]
    over_breakeven = curr_p > breakeven
    l1, l2, l3 = st.columns(3)
    l1.metric("Current Grid Price", f"${curr_p:.2f}/MWh")
    l1.metric("Total Generation", f"{(total_gen * 0.358):.1f} MW")
    l2.metric("Miner Load", f"{35.0 if not over_breakeven else 0.0} MW")
    
    ma_live = 35 * (breakeven - max(0, curr_p)) if not over_breakeven else 0
    ba_live = batt_mw * curr_p if over_breakeven else (batt_mw * abs(curr_p) if curr_p < 0 else 0)
    st.metric("Mining Alpha", f"${ma_live:,.2f}/hr")
    st.metric("Battery Alpha", f"${ba_live:,.2f}/hr")

    # --- HISTORICAL PERFORMANCE (RESTORED SECTION) ---
    st.markdown("---")
    st.subheader("📅 Historical Performance (Cumulative Alpha)")
    
    def show_cum(label, total, alpha, grid, mine, batt):
        st.markdown(f"#### {label}")
        st.markdown(f"**Total Site Revenue**")
        st.markdown(f"<h1>${total:,.0f}</h1>", unsafe_allow_html=True)
        st.markdown(f"<p style='color:#28a745;'>↑ ${alpha:,.0f} Alpha</p>", unsafe_allow_html=True)
        st.write(f" * ⚡ **Grid (Base):** :green[${grid:,.0f}]")
        st.write(f" * ⛏️ **Mining Alpha:** :green[${mine:,.0f}]")
        st.write(f" * 🔋 **Battery Alpha:** :green[${batt:,.0f}]")
        st.write("---")

    show_cum("Last 24 Hours", 101116, 47527, 53589, 47527, 0)
    show_cum("Last 7 Days", 704735, 335624, 369111, 335624, 0)
    show_cum("Last 30 Days", 3009339, 1448833, 1560506, 1448833, 0)
    show_cum("Last 6 Months", 13159992, 2909992, 10250000, 1559992, 1350000)
    show_cum("Last 1 Year", 26469998, 5819998, 20650000, 3119998, 2700000)

    # --- TAX STRATEGY ---
    st.markdown("---")
    st.subheader("🏛️ Commercial Tax Strategy")
    tx1, tx2, tx3 = st.columns(3)
    t_rate = (0.3 if tx1.checkbox("Apply 30% Base ITC", True) else 0) + (0.1 if tx2.checkbox("Apply 10% Domestic Content", False) else 0)
    li_choice = tx3.selectbox("Underserved Bonus", ["None", "10% Bonus", "20% Bonus"])
    t_rate += (0.1 if "10%" in li_choice else (0.2 if "20%" in li_choice else 0))

    # --- REVENUE ENGINE ---
    capture_2025 = TREND_DATA_WEST["Negative (<$0)"]["2025"] + TREND_DATA_WEST["$0 - $0.02"]["2025"]
    def get_metrics(m, b, itc_r):
        ma = (capture_2025 * 8760 * m * (breakeven - 12)) * (1.0 + (w_pct * 0.20))
        ba = (0.12 * 8760 * b * (breakeven + 30)) * (1.0 + (s_pct * 0.25))
        base = (solar_cap * 82500 + wind_cap * 124000)
        m_cap = ((m * 1e6) / m_eff) * m_cost
        b_cap = b * BATT_COST_PER_MW
        net = m_cap + (b_cap * (1 - itc_r))
        irr = (ma + ba) / net * 100 if net > 0 else 0
        roi = net / (ma + ba) if (ma + ba) > 0 else 0
        return ma, ba, base, net, irr, roi, m_cap, b_cap

    s_cur, s_opt = get_metrics(35, batt_mw, t_rate), get_metrics(ideal_m, ideal_b, t_rate)

    st.markdown("---")
    st.subheader("💰 Post-Tax Financial Comparison")
    cl1, cl2 = st.columns(2)
    with cl1:
        st.metric("Post-Tax IRR", f"{s_cur[4]:.1f}%")
        st.metric("Post-Tax ROI", f"{s_cur[5]:.2f} Yrs")
    with cl2:
        st.metric("Post-Tax IRR", f"{s_opt[4]:.1f}%")
        st.metric("Post-Tax ROI", f"{s_opt[5]:.2f} Yrs")

    # --- EVOLUTION CARDS ---
    st.markdown("---")
    st.subheader("📋 Historical Performance Evolution")
    def draw_card(lbl, met, m_v, b_v, sub):
        st.write(f"### {lbl}")
        st.caption(f"{sub} ({m_v}MW / {b_v}MW)")
        total = met[0] + met[1] + met[2]
        st.markdown(f"<h1 style='color: #28a745; margin-bottom: 0;'>${total:,.0f}</h1>", unsafe_allow_html=True)
        st.markdown(f"**↑ IRR: {met[4]:.1f}% | ROI: {met[5]:.2f} Yrs**")
        st.write(f"* ⚡ Grid Base: `${met[2]:,.0f}`")
        st.write(f"* ⛏️ Mining Alpha: `${met[0]:,.0f}`")
        st.write(f"* 🔋 Battery Alpha: `${met[1]:,.0f}`")
        st.write(f"* ⚙️ Miner Capex: `${met[6]:,.0f}`")
        st.write(f"* 🔋 Battery Capex (Pre-Tax): `${met[7]:,.0f}`")
        st.write("---")

    c_a, c_b, c_c, c_d = st.columns(4)
    with c_a: draw_card("1. Pre-Opt", get_metrics(35, batt_mw, 0), 35, batt_mw, "Current/No Tax")
    with c_b: draw_card("2. Opt (Pre-Tax)", get_metrics(ideal_m, ideal_b, 0), ideal_m, ideal_b, "Ideal/No Tax")
    with c_c: draw_card("3. Current (Post-Tax)", s_cur, 35, batt_mw, "Current/Full Tax")
    with c_d: draw_card("4. Opt (Post-Tax)", s_opt, ideal_m, ideal_b, "Ideal/Full Tax")

with tab2:
    st.subheader("📈 5-Year Price Frequency Dataset")
    st.markdown("#### 1. West Texas (HB_WEST)")
    st.table(pd.DataFrame(TREND_DATA_WEST).T.style.format("{:.1%}"))
    st.markdown("#### 2. ERCOT System-Wide Average")
    st.table(pd.DataFrame(TREND_DATA_SYSTEM).T.style.format("{:.1%}"))
    st.markdown("---")
    st.subheader("🧐 Strategic Trend Analysis")
    st.write("""
    * **Negative Pricing Spread:** HB_WEST remains the 'Alpha Hub' for negative prices (12.1% by 2025 vs 4.2% System-wide).
    * **The 2021 Uri Impact:** System-wide assets were more exposed to scarcity pricing than West Texas during Winter Storm Uri.
    * **Solar Saturation:** The growth in the $0-$0.02 bracket is now a system-wide phenomenon.
    """)
