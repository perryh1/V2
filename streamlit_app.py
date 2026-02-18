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

# --- 5-YEAR HISTORICAL FREQUENCY DATASET (HB_WEST) ---
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
    capture_2025 = TREND_DATA_WEST["Negative (<$0)"]["2025"] + TREND_DATA_WEST["$0 - $0.02"]["2025"]
    
    def get_simple_rev(m, b):
        # Operational Pivot: Miners for low price, Battery for high price
        ma = (capture_2025 * 8760 * m * (breakeven - 12)) * (1.0 + (w_pct * 0.20))
        # High-Price brackets (> $0.06/kWh approx) for Battery Supply
        ba = (0.12 * 8760 * b * (breakeven + 30)) * (1.0 + (s_pct * 0.25))
        return ma + ba

    cur_rev, idl_rev = get_simple_rev(35, batt_mw), get_simple_rev(ideal_m, ideal_b)
    st.metric("Annual Optimization Delta", f"${(idl_rev - cur_rev):,.0f}", delta=f"{((idl_rev - cur_rev)/cur_rev*100):.1f}% Upside")

    # --- LIVE POWER & PERFORMANCE (PIVOT LOGIC) ---
    st.markdown("---")
    st.subheader("📊 Live Power & Performance")
    curr_p = price_hist.iloc[-1]
    
    # Pivot Trigger: Price vs Breakeven
    over_breakeven = curr_p > breakeven
    
    l1, l2, l3 = st.columns(3)
    l1.metric("Current Grid Price", f"${curr_p:.2f}/MWh")
    l2.metric("Miner Status", "OFF (Market Peak)" if over_breakeven else "ON (Mining Alpha)")
    l3.metric("Battery Status", "SUPPLYING GRID" if over_breakeven else ("CHARGING" if curr_p < 0 else "IDLE"))

    # Earnings logic: If price is low, miners earn. If price is high, battery earns.
    ma_live = 35 * (breakeven - max(0, curr_p)) if not over_breakeven else 0
    ba_live = batt_mw * curr_p if over_breakeven else (batt_mw * abs(curr_p) if curr_p < 0 else 0)
    
    st.metric("Mining Alpha (Hourly)", f"${ma_live:,.2f}/hr")
    st.metric("Battery Alpha (Hourly)", f"${ba_live:,.2f}/hr")

    # --- TAX STRATEGY & EVOLUTION CARDS ---
    st.markdown("---")
    st.subheader("🏛️ Commercial Tax Strategy")
    tx1, tx2, tx3 = st.columns(3)
    t_rate = (0.3 if tx1.checkbox("Apply 30% Base ITC", True) else 0) + (0.1 if tx2.checkbox("Apply 10% Domestic Content", False) else 0)
    li_choice = tx3.selectbox("Underserved Bonus", ["None", "10% Bonus", "20% Bonus"])
    t_rate += (0.1 if "10%" in li_choice else (0.2 if "20%" in li_choice else 0))

    st.markdown("---")
    st.subheader("📋 Historical Performance Evolution")
    def get_metrics(m, b, itc):
        ma = (capture_2025 * 8760 * m * (breakeven - 12)) * (1.0 + (w_pct * 0.20))
        # Battery Supply revenue focused on hours > breakeven
        ba = (0.12 * 8760 * b * (breakeven + 30)) * (1.0 + (s_pct * 0.25))
        base = (solar_cap * 82500 + wind_cap * 124000)
        net = ((m*1e6)/m_eff)*m_cost + (b*BATT_COST_PER_MW*(1-itc))
        return ma, ba, base, net, (ma+ba)/net*100 if net > 0 else 0

    s1, s2, s3, s4 = get_metrics(35, batt_mw, 0), get_metrics(ideal_m, ideal_b, 0), get_metrics(35, batt_mw, t_rate), get_metrics(ideal_m, ideal_b, t_rate)
    
    def draw(lbl, met, m_v, b_v, sub):
        st.write(f"### {lbl}")
        st.caption(f"{sub} ({m_v}MW/{b_v}MW)")
        st.markdown(f"<h1 style='color: #28a745;'>${(met[0]+met[1]+met[2]):,.0f}</h1>", unsafe_allow_html=True)
        st.markdown(f"**↑ Alpha: ${(met[0]+met[1]):,.0f} | IRR: {met[4]:.1f}%**")
        st.write("---")

    c_a, c_b, c_c, c_d = st.columns(4)
    with c_a: draw("1. Pre-Opt", s1, 35, batt_mw, "Current/No Tax")
    with c_b: draw("2. Opt (Pre-Tax)", s2, ideal_m, ideal_b, "Ideal/No Tax")
    with c_c: draw("3. Current (Post-Tax)", s3, 35, batt_mw, "Current/Full Tax")
    with c_d: draw("4. Opt (Post-Tax)", s4, ideal_m, ideal_b, "Ideal/Full Tax")

with tab2:
    st.subheader("📈 5-Year Price Frequency (HB_WEST)")
    st.table(pd.DataFrame(TREND_DATA_WEST).T.style.format("{:.1%}"))
