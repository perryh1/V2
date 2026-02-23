import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import gridstatus
import os
import pickle
from datetime import datetime, timedelta

# --- Graceful Import for Enterprise API ---
try:
    import gridstatusio
    GS_ENTERPRISE_AVAILABLE = True
except ImportError:
    GS_ENTERPRISE_AVAILABLE = False

# --- 1. CORE SYSTEM CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Hybrid OS | Grid Intelligence")

DASHBOARD_PASSWORD = "123"
BATT_COST_PER_MW = 897404.0 
CORP_TAX_RATE = 0.21 
CACHE_FILE = "ercot_price_cache.pkl"
CACHE_EXPIRY_HOURS = 1

def load_cached_prices():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'rb') as f:
                data = pickle.load(f)
                if data['timestamp'] > datetime.now() - timedelta(hours=CACHE_EXPIRY_HOURS):
                    return data['prices']
        except:
            pass
    return None

def save_cached_prices(prices):
    try:
        with open(CACHE_FILE, 'wb') as f:
            pickle.dump({'prices': prices, 'timestamp': datetime.now()}, f)
    except:
        pass

# --- 2. AUTHENTICATION ---
if "password_correct" not in st.session_state: st.session_state.password_correct = False
def check_password():
    if st.session_state.password_correct: return True
    st.markdown("""<style>.stApp { background-color: #0e1117; display: grid; place-items: center; min-height: 100vh; }</style>""", unsafe_allow_html=True)
    pwd = st.text_input("Institutional Access Key", type="password")
    if st.button("Authenticate Session"):
        if pwd == DASHBOARD_PASSWORD: st.session_state.password_correct = True; st.rerun()
    return False
if not check_password(): st.stop()

# --- 3. SIDEBAR CONTROLS ---
st.sidebar.markdown("# Hybrid OS")
st.sidebar.caption("v14.5 Deployment")
st.sidebar.write("---")

st.sidebar.markdown("### 🔌 Gridstatus.io Integration")
gs_api_key = st.sidebar.text_input("API Key (gridstatus.io)", value="ca4d17f58f114c8aa7f60b2f33e2a581", type="password")
target_market = st.sidebar.selectbox("Live Telemetry Target", ["ERCOT (HB_WEST)", "SPP (Hardin MT Proxy)"])

st.sidebar.write("---")
st.sidebar.markdown("### ⚡ Generation Mix (Renewables)")
solar_cap = st.sidebar.slider("Solar Capacity (MW)", 0, 1000, 100)
wind_cap = st.sidebar.slider("Wind Capacity (MW)", 0, 1000, 100)
st.sidebar.write("---")
st.sidebar.markdown("### ⛏️ Miner Metrics")
m_cost = st.sidebar.slider("Miner Price ($/TH)", 1.0, 50.0, 20.00)
m_eff = st.sidebar.slider("Efficiency (J/TH)", 10.0, 35.0, 15.0)
hp_cents = st.sidebar.slider("Hashprice (¢/TH)", 1.0, 10.0, 4.0)
st.sidebar.write("---")
st.sidebar.markdown("### 🏛️ Starting Hardware")
m_load_in = st.sidebar.number_input("Starting Miner Load (MW)", value=0)
b_mw_in = st.sidebar.number_input("Starting Battery Size (MW)", value=0)

# --- 4. DATA PROCESSING ---
@st.cache_data(ttl=300)
def get_live_data(api_key, market):
    cached = load_cached_prices()
    if cached is not None: return cached
    end_date = pd.Timestamp.now(tz="US/Central")
    start_date = end_date - pd.Timedelta(days=365) # Extended to 1 Year for Table
    
    if api_key and GS_ENTERPRISE_AVAILABLE:
        try:
            client = gridstatusio.GridStatusClient(api_key=api_key)
            if "ERCOT" in market:
                df = client.get_dataset(dataset="ercot_spp_real_time_15_min", start=start_date, end=end_date)
                if df is not None and not df.empty:
                    series = df[df['Settlement Point'] == 'HB_WEST'].set_index('Interval Start').sort_index()['Settlement Point Price']
                    save_cached_prices(series)
                    return series
            elif "SPP" in market:
                df = client.get_dataset(dataset="spp_rtm_lmp", start=start_date, end=end_date)
                if df is not None and not df.empty:
                    series = df.set_index('Interval Start').sort_index()['LMP'] 
                    save_cached_prices(series)
                    return series
        except Exception as e:
            st.sidebar.error(f"API Error: {e}")
    elif api_key and not GS_ENTERPRISE_AVAILABLE:
        st.sidebar.warning("gridstatusio not installed. Using fallback data.")
        
    return pd.Series(np.random.uniform(5, 60, 8760 * 12)) 

price_hist = get_live_data(gs_api_key, target_market)
breakeven = (1e6 / m_eff) * (hp_cents / 100.0) / 24.0

def calculate_period_live_metrics(price_series, breakeven_val, ideal_m, ideal_b, days, w_pct, s_pct):
    try:
        data_points = int(days * 288)
        period_data = price_series.iloc[-data_points:] if len(price_series) >= data_points else price_series
        avg_price = period_data.mean()
        
        raw_mining = sum([max(0, breakeven_val - p) * ideal_m for p in period_data]) / 288.0
        raw_battery = sum([max(0, p - breakeven_val) * ideal_b for p in period_data]) / 288.0
        
        weighted_mining = raw_mining * (1.0 + (w_pct * 0.20))
        weighted_battery = raw_battery * (1.0 + (s_pct * 0.25))
        
        return weighted_mining, weighted_battery, avg_price
    except: return 0, 0, 0

# --- 5. DASHBOARD INTERFACE ---
t_baseload, t_hardin, t_evolution, t_tax, t_volatility, t_price_dsets = st.tabs([
    "🏭 Thermal Baseload OS", "🏔️ BTC and Storage Revenue", "📊 Renewable Evolution", "🏛️ Institutional Tax Strategy", "📈 Long-Term Volatility", "📊 Price Datasets"
])

# ==========================================
# THERMAL BASELOAD OS (HARDIN, MT)
# ==========================================
with t_baseload:
    st.markdown("### 🏭 100 MW Thermal Baseload Optimization (Hardin, MT)")
    st.write("Optimizing a 'Must-Run' thermal asset requires a synthetic floor to mitigate losses during negative pricing, and a peak multiplier (BESS) to capitalize on extreme summer scarcity.")
    
    coal_mw = 100
    coal_cost_mwh = 55.00
    
    required_efficiency = (1e6 * (hp_cents / 100.0)) / (coal_cost_mwh * 24.0)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Nameplate Capacity", f"{coal_mw} MW", "Must-Run")
    c2.metric("Production Cost", f"${coal_cost_mwh:.2f}/MWh", "- Fixed Sunk Cost", delta_color="inverse")
    with c3:
        st.metric("Miner Breakeven", f"${breakeven:.2f}/MWh", "Synthetic Floor")
        st.caption(f"**Hashprice Breakeven:** `{required_efficiency:.1f} J/TH`")
    c4.metric("Current Market Price", f"${price_hist.iloc[-1] if len(price_hist) > 0 else 0:.2f}/MWh")
    
    st.markdown("---")
    st.subheader("⚙️ Recommended Hardware Sizing & Optimal Capital Allocation")
    
    ideal_coal_miners = coal_mw
    ideal_coal_battery = int(coal_mw * 0.25)
    
    base_itc = 0.30
    energy_community_bonus = 0.10
    domestic_content = 0.10
    total_itc = base_itc + energy_community_bonus + domestic_content
    
    miner_capex_100mw = ideal_coal_miners * (1e6 / m_eff) * m_cost
    batt_capex_25mw_pre = ideal_coal_battery * BATT_COST_PER_MW
    batt_capex_25mw_post = batt_capex_25mw_pre * (1 - total_itc)
    
    pre_total = miner_capex_100mw + batt_capex_25mw_pre
    post_total = miner_capex_100mw + batt_capex_25mw_post
    
    m_alloc_pre = (miner_capex_100mw / pre_total) * 100
    b_alloc_pre = (batt_capex_25mw_pre / pre_total) * 100
    m_alloc_post = (miner_capex_100mw / post_total) * 100
    b_alloc_post = (batt_capex_25mw_post / post_total) * 100
    
    b1, b2, b3 = st.columns([1, 1, 1])
    with b1:
        st.markdown(f"**1. Capacity Ratio Sizing**")
        st.write(f"⛏️ Miners: `{ideal_coal_miners} MW`")
        st.write(f"🔋 Battery: `{ideal_coal_battery} MW`")
        st.caption("Matches 100% of plant nameplate for negative price defense, with a 25% peak multiplier for scarcity exports.")
    with b2:
        st.markdown("**2. Pre-Tax Capital Allocation**")
        st.write(f"For every **$100** spent:")
        st.write(f"⛏️ Miners: `${m_alloc_pre:.2f}`")
        st.write(f"🔋 Battery: `${b_alloc_pre:.2f}`")
        st.caption(f"Total Pre-Tax Capex: ${(pre_total/1e6):.1f}M")
    with b3:
        st.markdown("**3. Post-Tax Capital Allocation (ITC)**")
        st.write(f"For every **$100** spent:")
        st.write(f"⛏️ Miners: `${m_alloc_post:.2f}`")
        st.write(f"🔋 Battery: `${b_alloc_post:.2f}`")
        st.caption(f"Total Post-Tax Capex: ${(post_total/1e6):.1f}M (Saves ${(batt_capex_25mw_pre - batt_capex_25mw_post)/1e6:.1f}M)")

# ==========================================
# HARDIN BTC AND STORAGE REVENUE
# ==========================================
with t_hardin:
    st.markdown("### 🏔️ BTC and Storage Revenue")
    st.write("This dual-view matrix visualizes total gross revenue and net profit logic across 1 year of real-time telemetry. Net Profit incorporates the fixed $55/MWh sunk production cost of the thermal asset.")
    
    def get_hardin_metrics(series, days, breakeven_val, miner_mw, batt_mw, coal_cost):
        try:
            pts = int(days * 288) 
            data = series.iloc[-pts:] if len(series) >= pts else series
            if len(data) == 0: return 0, 0, 0, 0, 0, 0
            
            avg_p = data.mean()
            above_be = data[data > breakeven_val]
            below_be = data[data <= breakeven_val]
            num_segments = len(above_be)
            
            # GROSS REVENUE
            miner_rev = len(below_be) * breakeven_val * miner_mw / 12.0
            batt_rev = sum(above_be) * batt_mw / 12.0
            total_rev = miner_rev + batt_rev
            
            # NET PROFIT (Revenue - Coal Cost/Charging Opp Cost)
            miner_profit = len(below_be) * (breakeven_val - coal_cost) * miner_mw / 12.0
            batt_profit = sum(p - breakeven_val for p in above_be) * batt_mw / 12.0
            total_profit = miner_profit + batt_profit
            
            return avg_p, num_segments, miner_rev, batt_rev, total_rev, total_profit
        except:
            return 0, 0, 0, 0, 0, 0

    metrics = [
        get_hardin_metrics(price_hist, 1, breakeven, ideal_coal_miners, ideal_coal_battery, coal_cost_mwh),
        get_hardin_metrics(price_hist, 7, breakeven, ideal_coal_miners, ideal_coal_battery, coal_cost_mwh),
        get_hardin_metrics(price_hist, 30, breakeven, ideal_coal_miners, ideal_coal_battery, coal_cost_mwh),
        get_hardin_metrics(price_hist, 182, breakeven, ideal_coal_miners, ideal_coal_battery, coal_cost_mwh),
        get_hardin_metrics(price_hist, 365, breakeven, ideal_coal_miners, ideal_coal_battery, coal_cost_mwh)
    ]
    
    # Unpack for the chart
    m_revs = [m[2] for m in metrics]
    b_revs = [m[3] for m in metrics]
    
    col_table, col_chart = st.columns([1.2, 1])
    
    with col_table:
        hardin_df = pd.DataFrame({
            "Metric": ["Avg Grid Price", "Intervals > Breakeven", "Miner Revenue (BTC)", "Battery Revenue (Export)", "Total Revenue", "Total Profit"],
            "24 Hours": [f"${metrics[0][0]:.2f}", metrics[0][1], f"${metrics[0][2]:,.0f}", f"${metrics[0][3]:,.0f}", f"${metrics[0][4]:,.0f}", f"${metrics[0][5]:,.0f}"],
            "7 Days": [f"${metrics[1][0]:.2f}", metrics[1][1], f"${metrics[1][2]:,.0f}", f"${metrics[1][3]:,.0f}", f"${metrics[1][4]:,.0f}", f"${metrics[1][5]:,.0f}"],
            "30 Days": [f"${metrics[2][0]:.2f}", metrics[2][1], f"${metrics[2][2]:,.0f}", f"${metrics[2][3]:,.0f}", f"${metrics[2][4]:,.0f}", f"${metrics[2][5]:,.0f}"],
            "6 Months": [f"${metrics[3][0]:.2f}", metrics[3][1], f"${metrics[3][2]:,.0f}", f"${metrics[3][3]:,.0f}", f"${metrics[3][4]:,.0f}", f"${metrics[3][5]:,.0f}"],
            "1 Year": [f"${metrics[4][0]:.2f}", metrics[4][1], f"${metrics[4][2]:,.0f}", f"${metrics[4][3]:,.0f}", f"${metrics[4][4]:,.0f}", f"${metrics[4][5]:,.0f}"]
        })
        st.table(hardin_df.set_index("Metric"))
        
    with col_chart:
        fig = go.Figure(data=[
            go.Bar(name='BTC Revenue', x=['24H', '7D', '30D', '6M', '1Y'], y=m_revs, marker_color='#F7931A'),
            go.Bar(name='Storage Revenue', x=['24H', '7D', '30D', '6M', '1Y'], y=b_revs, marker_color='#0052FF')
        ])
        fig.update_layout(
            barmode='stack', 
            title="Gross Revenue Composition", 
            margin=dict(l=0, r=0, t=40, b=0), 
            paper_bgcolor='rgba(0,0,0,0)', 
            plot_bgcolor='rgba(0,0,0,0)',
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)

# ==========================================
# RETAINED TABS (RENEWABLES & ISO ANALYSIS)
# ==========================================
with t_evolution:
    st.markdown(f"### ⚙️ Renewable Performance Summary")
    curr_p = price_hist.iloc[-1] if len(price_hist) > 0 else 0
    total_gen = solar_cap + wind_cap
    s_pct = solar_cap / total_gen if total_gen > 0 else 0.5
    w_pct = wind_cap / total_gen if total_gen > 0 else 0.5
    ideal_m, ideal_b = int(total_gen * ((s_pct * 0.10) + (w_pct * 0.25))), int(total_gen * ((s_pct * 0.50) + (w_pct * 0.25)))

    l1, l2, l3, l4 = st.columns(4)
    l1.metric("Market Price", f"${curr_p:.2f}")
    l2.metric("Miner Breakeven", f"${breakeven:.2f}")
    l3.metric("Miner Status", "OFF" if m_load_in == 0 else ("ACTIVE" if curr_p < breakeven else "INACTIVE"))
    l4.metric("Total Generation", f"{(total_gen * 0.358):.1f} MW")

    st.markdown("---")
    st.subheader("📅 Comparative Alpha Tracking")
    show_comparison = st.toggle("Compare Actual (Live) vs. Historic Strategy", value=True)
    h1, h2, h3 = st.columns(3)
    
    TREND_DATA_WEST = {"Negative (<$0)": {"2025": 0.121}, "$0 - $0.02": {"2025": 0.335}}
    cap_2025 = 0.456 
    dm = (cap_2025 * 8760 * ideal_m * (breakeven - 12)) / 365 / (1.0 + (w_pct * 0.20))
    db = (0.12 * 8760 * ideal_b * (breakeven + 30)) / 365 / (1.0 + (s_pct * 0.25))

    periods = [("24H", 1), ("7D", 7), ("30D", 30)]
    for i, (lbl, days) in enumerate(periods):
        with [h1, h2, h3][i]:
            ma_live, ba_live, avg_p = calculate_period_live_metrics(price_hist, breakeven, ideal_m, ideal_b, days, w_pct, s_pct)
            ma_hist, ba_hist = (dm * days * (1.0 + (w_pct * 0.20))), (db * days * (1.0 + (s_pct * 0.25)))
            
            st.markdown(f"#### {lbl} Performance")
            st.metric("Avg Grid Price", f"${avg_p:.2f}")
            if show_comparison:
                st.write(f"**Live Alpha:** :green[${(ma_live + ba_live):,.0f}]")
                st.caption(f"⛏️ ${ma_live:,.0f} | 🔋 ${ba_live:,.0f}")
                st.write(f"**Historic Predict:** ${(ma_hist + ba_hist):,.0f}")
                delta = (ma_live + ba_live) - (ma_hist + ba_hist)
                st.caption(f"Variance: :{'green' if delta > 0 else 'red'}[${delta:,.0f}]")
            else:
                st.markdown(f"<h2 style='color:#28a745;'>${(ma_live + ba_live):,.0f}</h2>", unsafe_allow_html=True)
            st.write("---")

with t_tax:
    st.subheader("🏛️ Institutional Tax Strategy")
    st.markdown("---")
    tx1, tx2, tx3, tx4 = st.columns(4)
    itc_rate = (0.3 if tx1.checkbox("30% Base ITC", True) else 0) + (0.1 if tx2.checkbox("10% Domestic Content", False) else 0)
    itc_u_val = tx3.selectbox("Underserved Bonus", [0.0, 0.1, 0.2], format_func=lambda x: f"{int(x*100)}%")
    itc_total = itc_rate + itc_u_val
    macrs_on = tx4.checkbox("Apply 100% MACRS Bonus", True)

    def get_metrics(m, b, itc_v, mc_on):
        ma = (cap_2025 * 8760 * m * (breakeven - 12)) * (1.0 + (0.5 * 0.20))
        ba = (0.12 * 8760 * b * (breakeven + 30)) * (1.0 + (0.5 * 0.25))
        m_c = ((m * 1e6) / m_eff) * m_cost
        b_c = b * BATT_COST_PER_MW
        iv = b_c * itc_v
        ms = ((m_c + b_c) - (0.5 * iv)) * CORP_TAX_RATE if mc_on else 0
        nc = (m_c + b_c) - iv - ms
        irr, roi = (ma+ba)/nc*100 if nc > 0 else 0, nc/(ma+ba) if (ma+ba)>0 else 0
        return ma, ba, nc, irr, roi, m_c, b_c, iv, ms

    c00, c10, c0t, c1t = get_metrics(m_load_in, b_mw_in, 0, False), get_metrics(100, 25, 0, False), get_metrics(m_load_in, b_mw_in, itc_total, macrs_on), get_metrics(100, 25, itc_total, macrs_on)
    ca, cb, cc, cd = st.columns(4)
    def draw_card(col, lbl, met, m_v, b_v, sub):
        with col:
            st.write(f"### {lbl}"); st.caption(f"{sub} ({m_v}MW/{b_v}MW)")
            st.markdown(f"<h1 style='color: #28a745; margin-bottom: 0;'>${(met[0]+met[1]):,.0f}</h1>", unsafe_allow_html=True)
            st.markdown(f"**↑ IRR: {met[3]:.1f}% | Payback: {met[4]:.2f} Y**")
            st.write(f" * ⚙️ Miner Capex: `${met[5]:,.0f}`")
            st.write(f" * 🔋 Battery Capex: `${met[6]:,.0f}`")
            if met[7] > 0 or met[8] > 0: st.write(f" * 🛡️ **Shields (ITC+MACRS):** :green[(`-${(met[7]+met[8]):,.0f}`)]")
            st.write("---")
    draw_card(ca, "1. Baseline", c00, m_load_in, b_mw_in, "Current Setup")
    draw_card(cb, "2. Optimized", c10, 100, 25, "Ideal Ratio")
    draw_card(cc, "3. Strategy", c0t, m_load_in, b_mw_in, "Incentivized")
    draw_card(cd, "4. Full Alpha", c1t, 100, 25, "Full Strategy")

with t_volatility:
    st.subheader("📈 Institutional Volatility Analysis")
    iso_comparison = {
        "ISO": ["ERCOT", "CAISO", "PJM", "SPP"],
        "Negative 2025": ["12.1%", "14.5%", "1.2%", "5.8%"],
        "Sub-$0.04 2025": ["45.6%", "44.7%", "56.8%", "53.4%"],
        "Mining Arbitrage": ["45.6%", "63.2%", "16.8%", "40.3%"],
        "Peak Volatility": ["2.6%", "4.1%", "0.5%", "2.0%"],
        "Volatility Trend": ["📈 Growing", "📈 Rapid", "📈 Emerging", "📈 Moderate"],
        "2025 Rating": ["⭐⭐⭐⭐", "⭐⭐⭐⭐⭐", "⭐⭐", "⭐⭐⭐"]
    }
    st.dataframe(pd.DataFrame(iso_comparison), use_container_width=True)

with t_price_dsets:
    st.markdown("## 📊 Price Datasets")
    col_live, col_hist = st.columns(2)
    with col_live:
        st.markdown("**🕒 24-Hour Live-Time Price Data**")
        if len(price_hist) > 0:
            st.line_chart(price_hist.iloc[-288:]) 
        else:
            st.write("Waiting for telemetry data...")
    with col_hist:
        st.markdown("**📈 Historical Price Dataset**")
        if len(price_hist) > 0:
            st.line_chart(price_hist)
        else:
            st.write("Waiting for historical data...")
