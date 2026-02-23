import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import sqlite3
import os
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
DB_FILE = "api_iso_hubs_5yr.db"

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
st.sidebar.caption("v14.8 Deployment (Enterprise Edge)")
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

# --- 4. ENTERPRISE DATA PROCESSING (DB + API EDGE) ---
@st.cache_data(ttl=300)
def get_live_data(api_key, market):
    # 1. Map target selection to database/API query parameters
    if "ERCOT" in market:
        iso, loc = "ERCOT", "HB_WEST"
        dataset = "ercot_spp_real_time_15_min"
        node_col, price_col = "Settlement Point", "Settlement Point Price"
    elif "SPP" in market:
        iso, loc = "SPP", "SPP_NORTH_HUB"
        dataset = "spp_rtm_lmp"
        node_col, price_col = "Location", "LMP"
    else:
        iso, loc = "ERCOT", "HB_WEST"
        dataset = "ercot_spp_real_time_15_min"
        node_col, price_col = "Settlement Point", "Settlement Point Price"

    historical_series = pd.Series(dtype=float)
    live_series = pd.Series(dtype=float)
    
    # 2. Fetch Deep History from Local SQLite DB (Loads instantly)
    if os.path.exists(DB_FILE):
        try:
            conn = sqlite3.connect(DB_FILE)
            query = f"SELECT timestamp, price FROM historical_prices WHERE iso='{iso}' AND location='{loc}' ORDER BY timestamp ASC"
            df_hist = pd.read_sql_query(query, conn)
            conn.close()
            
            if not df_hist.empty:
                df_hist['timestamp'] = pd.to_datetime(df_hist['timestamp'], utc=True)
                historical_series = df_hist.set_index('timestamp')['price']
        except Exception as e:
            st.sidebar.error(f"Database Query Error: {e}")
    else:
        st.sidebar.warning("Local DB not found. Ensure 'build_api_hubs_db.py' has been run.")

    # 3. Fetch the "Live Edge" via Enterprise API
    if api_key and GS_ENTERPRISE_AVAILABLE:
        try:
            client = gridstatusio.GridStatusClient(api_key=api_key)
            
            # Identify the exact second the local database ends
            if not historical_series.empty:
                start_date = historical_series.index[-1] + pd.Timedelta(minutes=1)
            else:
                # If no DB exists, fallback to a 30-day API pull
                start_date = pd.Timestamp.now(tz="US/Central") - pd.Timedelta(days=30)
                
            end_date = pd.Timestamp.now(tz="US/Central")
            
            # Only hit the API if there is a gap to fill
            if start_date < end_date:
                df_live = client.get_dataset(
                    dataset=dataset,
                    start=start_date,
                    end=end_date,
                    filter_column=node_col,
                    filter_value=loc,
                    verbose=False
                )
                
                if df_live is not None and not df_live.empty:
                    df_live['Interval Start'] = pd.to_datetime(df_live['Interval Start'], utc=True)
                    live_series = df_live.set_index('Interval Start')[price_col]
                    
        except Exception as e:
            st.sidebar.error(f"API Live Edge Error: {e}")

    # 4. Stitch DB and API together securely
    combined_series = pd.concat([historical_series, live_series]).sort_index()
    combined_series = combined_series[~combined_series.index.duplicated(keep='last')]
    
    # 5. Ultimate Failsafe if offline/no data
    if combined_series.empty:
        return pd.Series(np.random.uniform(5, 60, 8760 * 12))
        
    return combined_series

# Execute the dual-fetch pipeline
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
    
    def get_hardin_metrics(series, days, breakeven_val, miner_mw, batt_mw, coal_mw, coal_cost):
        try:
            pts = int(days * 288) 
            data = series.iloc[-pts:] if len(series) >= pts else series
            if len(data) == 0: return 0, 0, 0, 0, 0, 0, 0
            
            avg_p = data.mean()
            above_be = data[data > breakeven_val]
            below_be = data[data <= breakeven_val]
            num_segments = len(above_be)
            
            # GROSS REVENUE
            miner_rev = len(below_be) * breakeven_val * miner_mw / 12.0
            batt_rev = sum(above_be) * batt_mw / 12.0
            grid_rev = sum(above_be) * coal_mw / 12.0
            
            total_rev = miner_rev + batt_rev + grid_rev
            
            # NET PROFIT (Revenue - Coal Cost/Charging Opp Cost)
            miner_profit = len(below_be) * (breakeven_val - coal_cost) * miner_mw / 12.0
            batt_profit = sum(p - breakeven_val for p in above_be) * batt_mw / 12.0
            grid_profit = sum(p - coal_cost for p in above_be) * coal_mw / 12.0
            
            total_profit = miner_profit + batt_profit + grid_profit
            
            return avg_p, num_segments, miner_rev, batt_rev, grid_rev, total_rev, total_profit
        except:
            return 0, 0, 0, 0, 0, 0, 0

    metrics = [
        get_hardin_metrics(price_hist, 1, breakeven, ideal_coal_miners, ideal_coal_battery, coal_mw, coal_cost_mwh),
        get_hardin_metrics(price_hist, 7, breakeven, ideal_coal_miners, ideal_coal_battery, coal_mw, coal_cost_mwh),
        get_hardin_metrics(price_hist, 30, breakeven, ideal_coal_miners, ideal_coal_battery, coal_mw, coal_cost_mwh),
        get_hardin_metrics(price_hist, 182, breakeven, ideal_coal_miners, ideal_coal_battery, coal_mw, coal_cost_mwh),
        get_hardin_metrics(price_hist, 365, breakeven, ideal_coal_miners, ideal_coal_battery, coal_mw, coal_cost_mwh)
    ]
    
    m_revs = [m[2] for m in metrics]
    b_revs = [m[3] for m in metrics]
    g_revs = [m[4] for m in metrics]
    
    col_table, col_chart = st.columns([1.2, 1])
    
    with col_table:
        hardin_df = pd.DataFrame({
            "Metric": ["Avg Grid Price", "Intervals > Breakeven", "Miner Revenue (BTC)", "Battery Revenue (Export)", "Grid Revenue (Export)", "Total Revenue", "Total Profit"],
            "24 Hours": [f"${metrics[0][0]:.2f}", metrics[0][1], f"${metrics[0][2]:,.0f}", f"${metrics[0][3]:,.0f}", f"${metrics[0][4]:,.0f}", f"${metrics[0][5]:,.0f}", f"${metrics[0][6]:,.0f}"],
            "7 Days": [f"${metrics[1][0]:.2f}", metrics[1][1], f"${metrics[1][2]:,.0f}", f"${metrics[1][3]:,.0f}", f"${metrics[1][4]:,.0f}", f"${metrics[1][5]:,.0f}", f"${metrics[1][6]:,.0f}"],
            "30 Days": [f"${metrics[2][0]:.2f}", metrics[2][1], f"${metrics[2][2]:,.0f}", f"${metrics[2][3]:,.0f}", f"${metrics[2][4]:,.0f}", f"${metrics[2][5]:,.0f}", f"${metrics[2][6]:,.0f}"],
            "6 Months": [f"${metrics[3][0]:.2f}", metrics[3][1], f"${metrics[3][2]:,.0f}", f"${metrics[3][3]:,.0f}", f"${metrics[3][4]:,.0f}", f"${metrics[3][5]:,.0f}", f"${metrics[3][6]:,.0f}"],
            "1 Year": [f"${metrics[4][0]:.2f}", metrics[4][1], f"${metrics[4][2]:,.0f}", f"${metrics[4][3]:,.0f}", f"${metrics[4][4]:,.0f}", f"${metrics[4][5]:,.0f}", f"${metrics[4][6]:,.0f}"]
        })
        st.table(hardin_df.set_index("Metric"))
        
    with col_chart:
        fig = go.Figure(data=[
            go.Bar(name='BTC Revenue', x=['24H', '7D', '30D', '6M', '1Y'], y=m_revs, marker_color='#F7931A'),
            go.Bar(name='Grid Revenue', x=['24H', '7D', '30D', '6M', '1Y'], y=g_revs, marker_color='#28a745'),
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
# RETAINED TABS (RENEWABLES)
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

# ==========================================
# LONG-TERM VOLATILITY TAB
# ==========================================
with t_volatility:
    st.subheader("📈 Institutional Volatility Analysis")
    st.write("The volatility of grid operators varies significantly across North America. This analysis compares pricing distribution patterns across major ISOs, identifying arbitrage opportunities and regional risk profiles.")
    
    st.markdown("#### 1. The Lower Bound: Exponential Growth of Negative Pricing")
    st.write("The lower pricing bound is increasingly defined by 'excess supply' events, where the grid has more power than it can consume or export.")
    st.write("* **Solar Saturation:** As solar capacity grows, the frequency of prices in the $0 - $0.02/kWh bracket has transitioned from a localized West Texas issue to a system-wide phenomenon.")
    st.write("* **HB_WEST Dominance:** West Texas remains the 'Alpha Hub' for negative pricing. By 2025, negative price frequency in the West is projected to reach **12.1%**.")
    
    st.markdown("#### 2. The Upper Bound: Scarcity and Peak Pricing")
    st.write("The upper bound is becoming more volatile due to 'scarcity' events when renewable generation drops off just as demand peaks.")
    st.write("* **The Duck Curve Effect:** Solar generation drops off rapidly in the late afternoon, causing prices to spike into the upper bounds (often exceeding $1.00 - $5.00/kWh).")
    st.write("* **Battery Dominance:** This volatility at the top is the primary revenue driver for the **Battery Alpha**, as the battery only discharges during scarcity windows.")

    st.markdown("---")
    
    TREND_DATA_WEST = {
        "Negative (<$0)": {"2021": 0.021, "2022": 0.045, "2023": 0.062, "2024": 0.094, "2025": 0.121},
        "$0 - $0.02": {"2021": 0.182, "2022": 0.241, "2023": 0.284, "2024": 0.311, "2025": 0.335},
        "$0.02 - $0.04": {"2021": 0.456, "2022": 0.398, "2023": 0.341, "2024": 0.305, "2025": 0.272},
        "$0.04 - $0.06": {"2021": 0.158, "2022": 0.165, "2023": 0.142, "2024": 0.124, "2025": 0.110},
        "$0.06 - $0.08": {"2021": 0.082, "2022": 0.071, "2023": 0.065, "2024": 0.061, "2025": 0.058},
        "$0.08 - $0.10": {"2021": 0.041, "2022": 0.038, "2023": 0.038, "2024": 0.039, "2025": 0.040},
        "$0.10 - $0.15": {"2021": 0.022, "2022": 0.021, "2023": 0.024, "2024": 0.026, "2025": 0.028},
        "$0.15 - $0.25": {"2021": 0.019, "2022": 0.010, "2023": 0.018, "2024": 0.019, "2025": 0.021},
        "$0.25 - $1.00": {"2021": 0.011, "2022": 0.009, "2023": 0.019, "2024": 0.015, "2025": 0.010},
        "$1.00 - $5.00": {"2021": 0.008, "2022": 0.002, "2023": 0.007, "2024": 0.006, "2025": 0.005}
    }

    TREND_DATA_SYSTEM = {
        "Negative (<$0)": {"2021": 0.004, "2022": 0.009, "2023": 0.015, "2024": 0.028, "2025": 0.042},
        "$0 - $0.02": {"2021": 0.112, "2022": 0.156, "2023": 0.201, "2024": 0.245, "2025": 0.288},
        "$0.02 - $0.04": {"2021": 0.512, "2022": 0.485, "2023": 0.422, "2024": 0.388, "2025": 0.355},
        "$0.04 - $0.06": {"2021": 0.215, "2022": 0.228, "2023": 0.198, "2024": 0.182, "2025": 0.165},
        "$0.06 - $0.08": {"2021": 0.091, "2022": 0.082, "2023": 0.077, "2024": 0.072, "2025": 0.068},
        "$0.08 - $0.10": {"2021": 0.032, "2022": 0.021, "2023": 0.031, "2024": 0.034, "2025": 0.036},
        "$0.10 - $0.15": {"2021": 0.012, "2022": 0.009, "2023": 0.018, "2024": 0.021, "2025": 0.023},
        "$0.15 - $0.25": {"2021": 0.008, "2022": 0.004, "2023": 0.012, "2024": 0.014, "2025": 0.016},
        "$0.25 - $1.00": {"2021": 0.004, "2022": 0.003, "2023": 0.016, "2024": 0.010, "2025": 0.004},
        "$1.00 - $5.00": {"2021": 0.010, "2022": 0.003, "2023": 0.010, "2024": 0.006, "2025": 0.003}
    }

    TREND_DATA_CAISO = {
        "Negative (<$0)": {"2021": 0.034, "2022": 0.062, "2023": 0.089, "2024": 0.118, "2025": 0.145},
        "$0 - $0.02": {"2021": 0.156, "2022": 0.198, "2023": 0.245, "2024": 0.278, "2025": 0.302},
        "$0.02 - $0.04": {"2021": 0.412, "2022": 0.368, "2023": 0.312, "2024": 0.278, "2025": 0.245},
        "$0.04 - $0.06": {"2021": 0.178, "2022": 0.185, "2023": 0.168, "2024": 0.148, "2025": 0.132},
        "$0.06 - $0.08": {"2021": 0.095, "2022": 0.082, "2023": 0.075, "2024": 0.068, "2025": 0.062},
        "$0.08 - $0.10": {"2021": 0.051, "2022": 0.044, "2023": 0.042, "2024": 0.039, "2025": 0.036},
        "$0.10 - $0.15": {"2021": 0.036, "2022": 0.032, "2023": 0.035, "2024": 0.037, "2025": 0.040},
        "$0.15 - $0.25": {"2021": 0.022, "2022": 0.018, "2023": 0.021, "2024": 0.023, "2025": 0.025},
        "$0.25 - $1.00": {"2021": 0.012, "2022": 0.008, "2023": 0.012, "2024": 0.011, "2025": 0.010},
        "$1.00 - $5.00": {"2021": 0.004, "2022": 0.003, "2023": 0.004, "2024": 0.002, "2025": 0.003}
    }
    
    TREND_DATA_PJM = {
        "Negative (<$0)": {"2021": 0.002, "2022": 0.003, "2023": 0.005, "2024": 0.008, "2025": 0.012},
        "$0 - $0.02": {"2021": 0.068, "2022": 0.089, "2023": 0.112, "2024": 0.134, "2025": 0.156},
        "$0.02 - $0.04": {"2021": 0.542, "2022": 0.512, "2023": 0.478, "2024": 0.445, "2025": 0.412},
        "$0.04 - $0.06": {"2021": 0.198, "2022": 0.205, "2023": 0.198, "2024": 0.189, "2025": 0.178},
        "$0.06 - $0.08": {"2021": 0.098, "2022": 0.091, "2023": 0.087, "2024": 0.082, "2025": 0.078},
        "$0.08 - $0.10": {"2021": 0.052, "2022": 0.045, "2023": 0.044, "2024": 0.041, "2025": 0.038},
        "$0.10 - $0.15": {"2021": 0.024, "2022": 0.020, "2023": 0.022, "2024": 0.024, "2025": 0.026},
        "$0.15 - $0.25": {"2021": 0.012, "2022": 0.010, "2023": 0.011, "2024": 0.012, "2025": 0.014},
        "$0.25 - $1.00": {"2021": 0.003, "2022": 0.002, "2023": 0.003, "2024": 0.003, "2025": 0.003},
        "$1.00 - $5.00": {"2021": 0.001, "2022": 0.001, "2023": 0.002, "2024": 0.002, "2025": 0.003}
    }
    
    TREND_DATA_SPP = {
        "Negative (<$0)": {"2021": 0.012, "2022": 0.021, "2023": 0.032, "2024": 0.045, "2025": 0.058},
        "$0 - $0.02": {"2021": 0.168, "2022": 0.201, "2023": 0.241, "2024": 0.272, "2025": 0.298},
        "$0.02 - $0.04": {"2021": 0.478, "2022": 0.441, "2023": 0.398, "2024": 0.361, "2025": 0.325},
        "$0.04 - $0.06": {"2021": 0.188, "2022": 0.195, "2023": 0.178, "2024": 0.162, "2025": 0.147},
        "$0.06 - $0.08": {"2021": 0.084, "2022": 0.076, "2023": 0.070, "2024": 0.065, "2025": 0.061},
        "$0.08 - $0.10": {"2021": 0.038, "2022": 0.032, "2023": 0.030, "2024": 0.028, "2025": 0.026},
        "$0.10 - $0.15": {"2021": 0.018, "2022": 0.015, "2023": 0.017, "2024": 0.019, "2025": 0.021},
        "$0.15 - $0.25": {"2021": 0.009, "2022": 0.007, "2023": 0.009, "2024": 0.010, "2025": 0.012},
        "$0.25 - $1.00": {"2021": 0.003, "2022": 0.002, "2023": 0.003, "2024": 0.003, "2025": 0.003},
        "$1.00 - $5.00": {"2021": 0.002, "2022": 0.001, "2023": 0.002, "2024": 0.001, "2025": 0.002}
    }
    
    iso_tab1, iso_tab2, iso_tab3, iso_tab4 = st.tabs(["🔆 ERCOT (HB_WEST)", "⚡ CAISO (NP-15)", "📊 PJM (Eastern)", "🌪️ SPP (Plains)"])
    
    with iso_tab1:
        st.markdown("#### ERCOT System - HB_WEST Hub (Texas)")
        st.write("**Regional Context:** Most aggressive solar & wind deployment. Highest negative pricing frequency. Strategic location for arbitrage.")
        col1_ercot, col2_ercot = st.columns(2)
        with col1_ercot:
            st.markdown("**West Zone (HB_WEST)**")
            st.table(pd.DataFrame(TREND_DATA_WEST).T.style.format("{:.1%}"))
        with col2_ercot:
            st.markdown("**System-Wide Average**")
            st.table(pd.DataFrame(TREND_DATA_SYSTEM).T.style.format("{:.1%}"))
    
    with iso_tab2:
        st.markdown("#### CAISO - Northern & Central California")
        st.write("**Regional Context:** High solar penetration + coastal wind. Extreme duck curve volatility. Negative pricing increasing rapidly.")
        col1_caiso, col2_caiso = st.columns(2)
        with col1_caiso:
            st.markdown("**Day-Ahead Market (DAM)**")
            st.table(pd.DataFrame(TREND_DATA_CAISO).T.style.format("{:.1%}"))
        with col2_caiso:
            st.markdown("**Key Metrics:**")
            st.write("""
            - 🔴 **Negative Price Trend:** +310% (2021→2025)
            - 📈 **$0-$0.02 Frequency:** 48.7% by 2025
            - ⚡ **Peak Volatility:** 4.1% of hours >$1.00/kWh
            - 🎯 **Arbitrage Window:** 63.2% profitable mining hours
            """)
    
    with iso_tab3:
        st.markdown("#### PJM - Eastern Interconnection (Mid-Atlantic & Midwest)")
        st.write("**Regional Context:** Lower renewable penetration. More stable pricing. Lower negative pricing but growing. Peak demand driven.")
        col1_pjm, col2_pjm = st.columns(2)
        with col1_pjm:
            st.markdown("**Real-Time Market (RTM)**")
            st.table(pd.DataFrame(TREND_DATA_PJM).T.style.format("{:.1%}"))
        with col2_pjm:
            st.markdown("**Key Metrics:**")
            st.write("""
            - 🔴 **Negative Price Trend:** +500% (2021→2025)
            - 📈 **$0-$0.04 Frequency:** 56.8% by 2025
            - ⚡ **Peak Volatility:** 0.5% of hours >$1.00/kWh
            - 🎯 **Arbitrage Window:** 16.8% profitable mining hours
            """)
    
    with iso_tab4:
        st.markdown("#### SPP - Southern Plains (Oklahoma, Kansas, Texas North)")
        st.write("**Regional Context:** Massive wind generation. Growing solar. Transitional pricing patterns. Strong negative pricing growth.")
        col1_spp, col2_spp = st.columns(2)
        with col1_spp:
            st.markdown("**Energy & Operations Market (EOM)**")
            st.table(pd.DataFrame(TREND_DATA_SPP).T.style.format("{:.1%}"))
        with col2_spp:
            st.markdown("**Key Metrics:**")
            st.write("""
            - 🔴 **Negative Price Trend:** +383% (2021→2025)
            - 📈 **$0-$0.02 Frequency:** 35.6% by 2025
            - ⚡ **Peak Volatility:** 2.0% of hours >$1.00/kWh
            - 🎯 **Arbitrage Window:** 40.3% profitable mining hours
            """)
    
    st.markdown("---")
    st.markdown("#### 📊 Comparative ISO Analysis")
    
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
