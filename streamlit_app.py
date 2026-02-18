import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import gridstatus
from datetime import datetime, timedelta

# --- 1. DESKTOP WIDE MODE & APP CONFIG ---
st.set_page_config(layout="wide", page_title="Midland Hybrid Alpha")

# --- CONFIGURATION ---
DASHBOARD_PASSWORD = "123"
BATT_COST_PER_MW = 897404.0 
CORP_TAX_RATE = 0.21 

# --- DATASETS ---
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

# --- LIVE DATA ---
@st.cache_data(ttl=300)
def get_live_data():
    try:
        iso = gridstatus.Ercot()
        df = iso.get_rtm_lmp(start=pd.Timestamp.now(tz="US/Central")-pd.Timedelta(days=31), end=pd.Timestamp.now(tz="US/Central"), verbose=False)
        return df[df['Location'] == 'HB_WEST'].set_index('Time').sort_index()['LMP']
    except: return pd.Series(np.random.uniform(15, 45, 744))

price_hist = get_live_data()

# --- APP TABS ---
tab1, tab2, tab3 = st.tabs(["📊 Performance Evolution", "🏛️ Tax Optimized Hardware", "📈 Long-Term Volatility"])

with tab1:
    st.markdown("### ⚙️ System Configuration")
    c1, c2, c3 = st.columns(3)
    with c1:
        solar_cap = st.slider("Solar Capacity (MW)", 0, 1000, 100)
        wind_cap = st.slider("Wind Capacity (MW)", 0, 1000, 100)
    with c2:
        # UPDATED DEFAULT STARTING POINTS
        m_cost = st.slider("Miner Cost ($/TH)", 1.0, 50.0, 20.00)
        m_eff = st.slider("Efficiency (J/TH)", 10.0, 35.0, 15.0)
    with c3:
        hp_cents = st.slider("Hashprice (¢/TH)", 1.0, 10.0, 4.0)
        m_load_input = st.number_input("Starting Miner Load (MW)", value=0)
        batt_mw_input = st.number_input("Starting Battery Size (MW)", value=0)
        breakeven = (1e6 / m_eff) * (hp_cents / 100.0) / 24.0

    st.markdown("---")
    curr_p = price_hist.iloc[-1]
    total_gen = solar_cap + wind_cap
    l1, l2, l3 = st.columns(3)
    l1.metric("Current Grid Price", f"${curr_p:.2f}/MWh")
    l2.metric("Miner Status", "OFF (No Load)" if m_load_input == 0 else ("ON" if curr_p < breakeven else "OFF"))
    ma_live = m_load_input * (breakeven - max(0, curr_p)) if (m_load_input > 0 and curr_p < breakeven) else 0
    ba_live = batt_mw_input * curr_p if (batt_mw_input > 0 and curr_p > breakeven) else 0
    st.metric("Mining Alpha", f"${ma_live:,.2f}/hr")
    st.metric("Battery Alpha", f"${ba_live:,.2f}/hr")

    st.markdown("---")
    st.subheader("🎯 Hybrid Optimization Engine")
    s_pct = solar_cap / total_gen if total_gen > 0 else 0.5
    w_pct = wind_cap / total_gen if total_gen > 0 else 0.5
    ideal_m, ideal_b = int(total_gen * ((s_pct * 0.10) + (w_pct * 0.25))), int(total_gen * ((s_pct * 0.50) + (w_pct * 0.25)))
    
    col_a, col_b = st.columns([1, 2])
    with col_a:
        st.write(f"**Ideal Sizing:** {ideal_m}MW Miners | {ideal_b}MW Battery")
        capture_2025 = TREND_DATA_WEST["Negative (<$0)"]["2025"] + TREND_DATA_WEST["$0 - $0.02"]["2025"]
        mining_yield_annual = (capture_2025 * 8760 * ideal_m * (breakeven - 12)) * (1.0 + (w_pct * 0.20))
        battery_yield_annual = (0.12 * 8760 * ideal_b * (breakeven + 30)) * (1.0 + (s_pct * 0.25))
        cur_rev = (total_gen * 103250) * 0.65
        idl_total_alpha = mining_yield_annual + battery_yield_annual
        st.metric("Annual Optimization Delta", f"${idl_total_alpha:,.0f}")

    st.markdown("---")
    h1, h2, h3, h4, h5 = st.columns(5)
    daily_m_a, daily_b_a = mining_yield_annual / 365, battery_yield_annual / 365
    def show_split_cum(col, label, days, base_rev):
        scale_f = (total_gen / 200); c_total = (base_rev * scale_f) * 0.65
        m_a, b_a = daily_m_a * days, daily_b_a * days
        with col:
            st.markdown(f"#### {label}")
            st.markdown(f"**Grid Base Revenue**")
            st.markdown(f"<h2 style='margin-bottom:0;'>${c_total:,.0f}</h2>", unsafe_allow_html=True)
            st.markdown(f"<p style='color:#28a745; margin-bottom:0;'>↑ ${(m_a + b_a):,.0f} Alpha Potential</p>", unsafe_allow_html=True)
            st.write(f" * ⛏️ Mining: `${m_a:,.0f}` | 🔋 Battery: `${b_a:,.0f}`")
    show_split_cum(h1, "24H", 1, 101116); show_split_cum(h2, "7D", 7, 704735); show_split_cum(h3, "30D", 30, 3009339)
    show_split_cum(h4, "6M", 182, 13159992); show_split_cum(h5, "1Y", 365, 26469998)

with tab2:
    st.subheader("🏛️ Tax Optimized Hardware")
    st.write("---")
    t1, t2, t3, t4 = st.columns(4)
    itc_r = (0.3 if t1.checkbox("30% Base ITC", True) else 0) + (0.1 if t2.checkbox("10% Domestic Bonus", False) else 0) + t3.selectbox("Underserved Bonus", [0.0, 0.1, 0.2])
    apply_macrs = t4.checkbox("Apply 100% Bonus MACRS (Yr 1)", True)

    def get_metrics(m, b, itc_v, macrs_on):
        ma = (capture_2025 * 8760 * m * (breakeven - 12)) * (1.0 + (w_pct * 0.20))
        ba = (0.12 * 8760 * b * (breakeven + 30)) * (1.0 + (s_pct * 0.25))
        base_grid = (solar_cap * 82500 + wind_cap * 124000)
        m_cap = ((m * 1e6) / m_eff) * m_cost
        b_cap = b * BATT_COST_PER_MW
        itc_val = b_cap * itc_v
        macrs_shield = ((m_cap + b_cap) - (0.5 * itc_val)) * CORP_TAX_RATE if macrs_on else 0
        net_capex = (m_cap + b_cap) - itc_val - macrs_shield
        irr, roi = (ma+ba)/net_capex*100 if net_capex > 0 else 0, net_capex/(ma+ba) if (ma+ba)>0 else 0
        return ma, ba, base_grid, net_capex, irr, roi, m_cap, b_cap, itc_val, macrs_shield

    s00, s10, s0t, s1t = get_metrics(m_load_input, batt_mw_input, 0, False), get_metrics(ideal_m, ideal_b, 0, False), get_metrics(m_load_input, batt_mw_input, itc_r, apply_macrs), get_metrics(ideal_m, ideal_b, itc_r, apply_macrs)
    ca, cb, cc, cd = st.columns(4)
    def draw_card(col, lbl, met, m_v, b_v, sub):
        with col:
            st.write(f"### {lbl}"); st.caption(f"{sub} ({m_v}MW/{b_v}MW)")
            st.markdown(f"<h1 style='color: #28a745; margin-bottom: 0;'>${(met[0]+met[1]+met[2]):,.0f}</h1>", unsafe_allow_html=True)
            st.markdown(f"**↑ IRR: {met[4]:.1f}% | ROI: {met[5]:.2f} Yrs**")
            st.write(f" * ⛏️ Mining Alpha: `${met[0]:,.0f}` | 🔋 Battery Alpha: `${met[1]:,.0f}`")
            st.write(f" * ⚙️ Miner Capex: `${met[6]:,.0f}` | 🔋 Battery Capex: `${met[7]:,.0f}`")
            if met[8] > 0 or met[9] > 0:
                st.write(f" * 🛡️ **Tax Shields:** :green[(`-${(met[8]+met[9]):,.0f}`)]")
            st.write("---")
    draw_card(ca, "1. Pre-Opt", s00, m_load_input, batt_mw_input, "Baseline")
    draw_card(cb, "2. Opt (Pre-Tax)", s10, ideal_m, ideal_b, "Optimized")
    draw_card(cc, "3. Current (Post-Tax)", s0t, m_load_input, batt_mw_input, "Tax Strategy")
    draw_card(cd, "4. Opt (Post-Tax)", s1t, ideal_m, ideal_b, "Full Alpha")

with tab3:
    st.subheader("📈 Long-Term Volatility")
    st.table(pd.DataFrame(TREND_DATA_WEST).T.style.format("{:.1%}"))
