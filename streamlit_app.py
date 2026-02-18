import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import gridstatus
from datetime import datetime, timedelta

# --- 1. CORE SYSTEM CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Hybrid OS | Grid Intelligence")

DASHBOARD_PASSWORD = "123"
BATT_COST_PER_MW = 897404.0 
CORP_TAX_RATE = 0.21 

# --- 2. EXECUTIVE AUTHENTICATION PORTAL ---
if "password_correct" not in st.session_state: 
    st.session_state.password_correct = False

def check_password():
    if st.session_state.password_correct: return True
    
    st.markdown("""
        <style>
        .stApp { background-color: #f8f9fa; }
        .login-container {
            max-width: 500px;
            margin: 80px auto;
            padding: 0;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.08);
            text-align: center;
            overflow: hidden;
            border: 1px solid #e0e0e0;
        }
        .brand-header {
            background-color: #ffffff;
            padding: 50px 20px;
            border-bottom: 1px solid #f0f0f0;
            margin-bottom: 30px;
        }
        .brand-text {
            color: #1a1a1a;
            font-family: 'Inter', sans-serif;
            font-weight: 800;
            font-size: 42px;
            letter-spacing: -1px;
            margin: 0;
        }
        .login-content { padding: 0 40px 40px 40px; }
        .main-title {
            color: #1a1a1a;
            font-family: 'Inter', sans-serif;
            font-weight: 700;
            font-size: 24px;
            margin-bottom: 4px;
            text-align: left;
        }
        .sub-title {
            color: #6c757d;
            font-family: 'Inter', sans-serif;
            font-size: 14px;
            margin-bottom: 24px;
            text-align: left;
        }
        </style>
    """, unsafe_allow_html=True)

    _, col_mid, _ = st.columns([1, 1.2, 1])
    with col_mid:
        st.markdown(f'''
            <div class="login-container">
                <div class="brand-header"><p class="brand-text">Hybrid OS</p></div>
                <div class="login-content">
                    <p class="main-title">Grid Alpha</p>
                    <p class="sub-title">Hybrid Asset Optimization & Yield Analytics</p>
        ''', unsafe_allow_html=True)
        pwd = st.text_input("Institutional Access Key", type="password", label_visibility="collapsed")
        if st.button("Authenticate Session", use_container_width=True, type="primary"):
            if pwd == DASHBOARD_PASSWORD:
                st.session_state.password_correct = True
                st.rerun()
            else:
                st.error("Authentication Failed")
        st.markdown('</div></div>', unsafe_allow_html=True)
    return False

if not check_password(): st.stop()

# --- 3. PERSISTENT SIDEBAR BRANDING ---
st.sidebar.markdown("# Hybrid OS")
st.sidebar.caption("v12.6 Deployment")
st.sidebar.write("---")

# --- 4. GLOBAL DATASETS ---
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

@st.cache_data(ttl=300)
def get_live_data():
    try:
        iso = gridstatus.Ercot()
        df = iso.get_rtm_lmp(start=pd.Timestamp.now(tz="US/Central")-pd.Timedelta(days=31), end=pd.Timestamp.now(tz="US/Central"), verbose=False)
        return df[df['Location'] == 'HB_WEST'].set_index('Time').sort_index()['LMP']
    except: return pd.Series(np.random.uniform(15, 45, 744))

price_hist = get_live_data()

# --- 5. DASHBOARD TABS ---
t_evolution, t_tax, t_volatility = st.tabs(["📊 Performance Evolution", "🏛️ Institutional Tax Strategy", "📈 Long-Term Volatility"])

with t_evolution:
    st.sidebar.markdown("### System Inputs")
    solar_cap = st.sidebar.slider("Solar Capacity (MW)", 0, 1000, 100)
    wind_cap = st.sidebar.slider("Wind Capacity (MW)", 0, 1000, 100)
    m_cost = st.sidebar.slider("Miner Price ($/TH)", 1.0, 50.0, 20.00)
    m_eff = st.sidebar.slider("Efficiency (J/TH)", 10.0, 35.0, 15.0)
    hp_cents = st.sidebar.slider("Hashprice (¢/TH)", 1.0, 10.0, 4.0)
    
    st.markdown("### ⚙️ Institutional Configuration")
    c1, c2 = st.columns(2)
    m_load_in = c1.number_input("Current Miner Load (MW)", value=0)
    b_mw_in = c2.number_input("Current Battery Size (MW)", value=0)
    breakeven = (1e6 / m_eff) * (hp_cents / 100.0) / 24.0

    st.markdown("---")
    curr_p = price_hist.iloc[-1]
    total_gen = solar_cap + wind_cap
    l1, l2, l3 = st.columns(3)
    l1.metric("Current Market Price", f"${curr_p:.2f}/MWh")
    l1.metric("Site Generation", f"{(total_gen * 0.358):.1f} MW")
    l2.metric("Miner Status", "OFF" if m_load_in == 0 else ("ACTIVE" if curr_p < breakeven else "INACTIVE"))
    ma_live = m_load_in * (breakeven - max(0, curr_p)) if (m_load_in > 0 and curr_p < breakeven) else 0
    ba_live = b_mw_in * curr_p if (b_mw_in > 0 and curr_p > breakeven) else 0
    l3.metric("Mining Alpha", f"${ma_live:,.2f}/hr")
    l3.metric("Battery Alpha", f"${ba_live:,.2f}/hr")

    st.markdown("---")
    st.subheader("🎯 Optimization Engine")
    s_pct = solar_cap / total_gen if total_gen > 0 else 0.5
    w_pct = wind_cap / total_gen if total_gen > 0 else 0.5
    ideal_m, ideal_b = int(total_gen * ((s_pct * 0.10) + (w_pct * 0.25))), int(total_gen * ((s_pct * 0.50) + (w_pct * 0.25)))
    
    col_a, col_b = st.columns([1, 2])
    with col_a:
        st.write(f"**Target Sizing:** {ideal_m}MW Miners | {ideal_b}MW Battery")
        cap_2025 = TREND_DATA_WEST["Negative (<$0)"]["2025"] + TREND_DATA_WEST["$0 - $0.02"]["2025"]
        m_yield_yr = (cap_2025 * 8760 * ideal_m * (breakeven - 12)) * (1.0 + (w_pct * 0.20))
        b_yield_yr = (0.12 * 8760 * ideal_b * (breakeven + 30)) * (1.0 + (s_pct * 0.25))
        idl_alpha = m_yield_yr + b_yield_yr
        st.metric("Annual Strategy Delta", f"${idl_alpha:,.0f}")
    with col_b:
        cur_rev_base = (total_gen * 103250) * 0.65
        # ALIGNED COLOR PALETTE: Institutional Dark Gray and Corporate Blue
        fig = go.Figure(data=[
            go.Bar(name='Baseline', x=['Revenue'], y=[cur_rev_base], marker_color='#E0E0E0'),
            go.Bar(name='Hybrid Optimized', x=['Revenue'], y=[cur_rev_base + idl_alpha], marker_color='#0052FF')
        ])
        fig.update_layout(barmode='group', height=200, margin=dict(t=0, b=0, l=0, r=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("📅 Historical Alpha Potential (Revenue Split)")
    h1, h2, h3, h4, h5 = st.columns(5)
    dm, db = m_yield_yr / 365, b_yield_yr / 365

    def show_split(col, lbl, days, base):
        sc = (total_gen / 200); cr = (base * sc) * 0.65
        ma, ba = dm * days, db * days
        with col:
            st.markdown(f"#### {lbl}")
            st.markdown(f"**Grid Baseline**")
            st.markdown(f"<h2 style='margin-bottom:0;'>${cr:,.0f}</h2>", unsafe_allow_html=True)
            st.markdown(f"<p style='color:#28a745; margin-bottom:0;'>↑ ${(ma + ba):,.0f} Alpha Potential</p>", unsafe_allow_html=True)
            st.write(f" * ⛏️ Mining: `${ma:,.0f}`")
            st.write(f" * 🔋 Battery: `${ba:,.0f}`")
            st.write("---")

    show_split(h1, "24H", 1, 101116); show_split(h2, "7D", 7, 704735); show_split(h3, "30D", 30, 3009339)
    show_split(h4, "6M", 182, 13159992); show_split(h5, "1Y", 365, 26469998)

with t_tax:
    st.subheader("🏛️ Institutional Tax Strategy")
    tx1, tx2, tx3, tx4 = st.columns(4)
    itc_rate = (0.3 if tx1.checkbox("30% Base ITC", True) else 0) + (0.1 if tx2.checkbox("10% Domestic Content", False) else 0)
    itc_u_val = tx3.selectbox("Underserved Bonus", [0.0, 0.1, 0.2], format_func=lambda x: f"{int(x*100)}%")
    itc_total = itc_rate + itc_u_val
    macrs_on = tx4.checkbox("Apply 100% MACRS Bonus", True)

    def get_metrics(m, b, itc_v, mc_on):
        ma = (cap_2025 * 8760 * m * (breakeven - 12)) * (1.0 + (w_pct * 0.20))
        ba = (0.12 * 8760 * b * (breakeven + 30)) * (1.0 + (s_pct * 0.25))
        m_c = ((m * 1e6) / m_eff) * m_cost
        b_c = b * BATT_COST_PER_MW
        iv = b_c * itc_v
        ms = ((m_c + b_c) - (0.5 * iv)) * CORP_TAX_RATE if mc_on else 0
        nc = (m_c + b_c) - iv - ms
        irr, roi = (ma+ba)/nc*100 if nc > 0 else 0, nc/(ma+ba) if (ma+ba)>0 else 0
        return ma, ba, nc, irr, roi, m_c, b_c, iv, ms

    cr_base_val = (total_gen * 103250) * 0.65
    c00, c10, c0t, c1t = get_metrics(m_load_in, b_mw_in, 0, False), get_metrics(ideal_m, ideal_b, 0, False), get_metrics(m_load_in, b_mw_in, itc_total, macrs_on), get_metrics(ideal_m, ideal_b, itc_total, macrs_on)
    ca, cb, cc, cd = st.columns(4)
    
    def draw_card(col, lbl, met, m_v, b_v, sub):
        with col:
            st.write(f"### {lbl}"); st.caption(f"{sub} ({m_v}MW/{b_v}MW)")
            st.markdown(f"<h1 style='color: #28a745; margin-bottom: 0;'>${(met[0]+met[1]+cr_base_val):,.0f}</h1>", unsafe_allow_html=True)
            st.markdown(f"**↑ IRR: {met[3]:.1f}% | Payback: {met[4]:.2f} Y**")
            st.write(f" * ⚙️ Miner Capex: `${met[5]:,.0f}`")
            st.write(f" * 🔋 Battery Capex: `${met[6]:,.0f}`")
            if met[7] > 0 or met[8] > 0: st.write(f" * 🛡️ **Shields (ITC+MACRS):** :green[(`-${(met[7]+met[8]):,.0f}`)]")
            st.write("---")
            
    draw_card(ca, "1. Baseline", c00, m_load_in, b_mw_in, "Current Setup")
    draw_card(cb, "2. Optimized", c10, ideal_m, ideal_b, "Ideal Ratio")
    draw_card(cc, "3. Strategy", c0t, m_load_in, b_mw_in, "Incentivized")
    draw_card(cd, "4. Full Alpha", c1t, ideal_m, ideal_b, "Full Strategy")

with t_volatility:
    st.subheader("📈 Institutional Volatility Analysis")
    st.write("ERCOT’s grid is shifting toward a **binary state** of extreme excess or scarcity. This volatility spread favors hybrid assets over pure generators.")
    
    # DUAL TABLES RESTORED
    v_c1, v_c2 = st.columns(2)
    with v_c1:
        st.markdown("#### West Zone (HB_WEST) Distribution")
        st.table(pd.DataFrame(TREND_DATA_WEST).T.style.format("{:.1%}"))
    with v_c2:
        st.markdown("#### ERCOT System-Wide Distribution")
        st.table(pd.DataFrame(TREND_DATA_SYSTEM).T.style.format("{:.1%}"))
        
    st.markdown("---")
    st.subheader("🧐 Strategic Summary")
    st.write("""
    * **Lower Bound Expansion:** Sub-2¢ pricing is now a system-wide trend. HB_WEST negative frequency is projected to hit **12.1%** by 2025—3x the system average.
    * **Scarcity Optimization:** Late afternoon 'Duck Curve' drop-offs cause scarcity spikes, often exceeding $1.00/kWh. This is the primary revenue driver for **Battery Alpha**.
    """)
    st.table(pd.DataFrame({
        "Price Category": ["Negative (<$0)", "$0 - $0.02", "High ($1.00+)"],
        "2021 Frequency (West)": ["2.1%", "18.2%", "0.8%"],
        "2025 Frequency (West)": ["12.1%", "33.5%", "0.5% (Proj)"],
        "Strategic Pivot": ["Mining Alpha", "Fuel Saturation", "Battery Alpha"]
    }).set_index("Price Category"))
