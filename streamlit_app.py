import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import gridstatus
import gridstatusio # NEW: Enterprise API Client
import os
import pickle
from datetime import datetime, timedelta

# --- 1. CORE SYSTEM CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Hybrid OS | Grid Intelligence")

DASHBOARD_PASSWORD = "123"
BATT_COST_PER_MW = 897404.0 
CORP_TAX_RATE = 0.21 
CACHE_FILE = "ercot_price_cache.pkl"
CACHE_EXPIRY_HOURS = 1

# --- CACHE FUNCTIONS ---
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

# --- 2. THE "CENTRAL HUB" AUTHENTICATION PORTAL ---
if "password_correct" not in st.session_state: 
    st.session_state.password_correct = False

def check_password():
    if st.session_state.password_correct: return True
    
    st.markdown("""
        <style>
        .stApp { background-color: #0e1117; display: grid; place-items: center; min-height: 100vh; }
        .auth-container {
            width: 95%; max-width: 900px; display: flex; flex-direction: row;
            background: #161b22; border-radius: 12px; border: 1px solid #30363d;
            overflow: hidden; box-shadow: 0 25px 50px rgba(0,0,0,0.5);
        }
        .auth-branding {
            background-color: #262730; padding: 60px 40px; flex: 1;
            display: flex; flex-direction: column; justify-content: center;
            border-right: 1px solid #3d3f4b;
        }
        .auth-form { flex: 1.5; padding: 60px; background-color: #161b22; }
        .brand-text { color: #ffffff; font-family: 'Inter', sans-serif; font-weight: 800; font-size: 42px; margin: 0; }
        .version-text { color: #808495; font-size: 14px; margin-top: 5px; }
        .auth-header { color: #ffffff; font-weight: 700; font-size: 28px; margin-bottom: 8px; }
        .auth-sub { color: #8b949e; font-size: 15px; margin-bottom: 30px; }
        .brief-section { color: #c9d1d9; font-size: 14px; line-height: 1.7; margin-bottom: 35px; border-left: 3px solid #0052FF; padding-left: 20px; }
        .brief-title { color: #58a6ff; font-weight: 600; font-size: 12px; text-transform: uppercase; margin-bottom: 12px; letter-spacing: 1.2px; }
        @media (max-width: 800px) {
            .auth-container { flex-direction: column; margin: 20px; }
            .auth-branding { padding: 40px; border-right: none; border-bottom: 1px solid #3d3f4b; }
            .auth-form { padding: 40px 30px; }
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="auth-container">', unsafe_allow_html=True)
    st.markdown('<div class="auth-branding"><p class="brand-text">Hybrid OS</p><p class="version-text">v14.1 Deployment</p></div>', unsafe_allow_html=True)
    st.markdown('<div class="auth-form">', unsafe_allow_html=True)
    st.markdown('<p class="auth-header">Executive Access</p><p class="auth-sub">Grid Intelligence & Asset Optimization Portal</p>', unsafe_allow_html=True)
    st.markdown('<p class="brief-title">Strategic Value Proposition</p>', unsafe_allow_html=True)
    st.markdown("""
    <div class="brief-section">
        • <b>Dynamic Arbitrage:</b> Identifies high-alpha windows where compute load outperforms spot market exports.<br><br>
        • <b>Yield Optimization:</b> Mathematically ideal BESS-to-Compute ratios calibrated to specific generation sources (Renewable & Thermal).<br><br>
        • <b>Financial Engineering:</b> Integrated ITC and MACRS tax shields for institutional-grade projections.
    </div>
    """, unsafe_allow_html=True)
    pwd = st.text_input("Institutional Access Key", type="password")
    if st.button("Authenticate Session", use_container_width=True, type="primary"):
        if pwd == DASHBOARD_PASSWORD:
            st.session_state.password_correct = True
            st.rerun()
        else:
            st.error("Authentication Failed")
    st.markdown('</div></div>', unsafe_allow_html=True)
    return False

if not check_password(): st.stop()

# --- 3. PERSISTENT SIDEBAR CONTROLS ---
st.sidebar.markdown("# Hybrid OS")
st.sidebar.caption("v14.1 Deployment")
st.sidebar.write("---")

st.sidebar.markdown("### 🔌 Gridstatus.io Integration")
gs_api_key = st.sidebar.text_input("API Key (gridstatus.io)", type="password")
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

# --- 4. DATA PROCESSING & CACHING ---
TREND_DATA_WEST = {
    "Negative (<$0)": {"2021": 0.021, "2025": 0.121},
    "$0 - $0.02": {"2021": 0.182, "2025": 0.335}
}

@st.cache_data(ttl=300)
def get_live_data(api_key, market):
    """Fetch real-time data using gridstatus.io API if key is present, else use fallback."""
    cached = load_cached_prices()
    if cached is not None: return cached

    end_date = pd.Timestamp.now(tz="US/Central")
    start_date = end_date - pd.Timedelta(days=30) # Fetch 30 days of 5-min intervals for accuracy

    # Use Gridstatus.io Enterprise API
    if api_key:
        try:
            client = gridstatusio.GridStatusClient(api_key=api_key)
            if "ERCOT" in market:
                df = client.get_dataset(
                    dataset="ercot_spp_real_time_15_min",
                    start=start_date,
                    end=end_date
                )
                if df is not None and not df.empty:
                    series = df[df['Settlement Point'] == 'HB_WEST'].set_index('Interval Start').sort_index()['Settlement Point Price']
                    save_cached_prices(series)
                    return series
            elif "SPP" in market:
                df = client.get_dataset(
                    dataset="spp_rtm_lmp",
                    start=start_date,
                    end=end_date
                )
                if df is not None and not df.empty:
                    # Using a generic SPP settlement location proxy until specific Hardin node is requested
                    series = df.set_index('Interval Start').sort_index()['LMP'] 
                    save_cached_prices(series)
                    return series
        except Exception as e:
            st.sidebar.error(f"API Error: {e}")

    # Fallback to public Gridstatus library scraper if no API key or API fails
    try:
        iso = gridstatus.Ercot()
        df = iso.get_rtm_lmp(start=start_date, end=end_date, verbose=False)
        if df is not None and len(df) > 0:
            series = df[df['Location'] == 'HB_WEST'].set_index('Time').sort_index()['LMP']
            save_cached_prices(series)
            return series
    except:
        pass

    # Final fallback simulation for uninterrupted UI development
    return pd.Series(np.random.uniform(5, 60, 8760)) 

# Execute Data Fetch
price_hist = get_live_data(gs_api_key, target_market)
breakeven = (1e6 / m_eff) * (hp_cents / 100.0) / 24.0

def calculate_period_live_metrics(price_series, breakeven_val, ideal_m, ideal_b, days, w_pct, s_pct):
    try:
        data_points = int(days * 288) # 288 5-min intervals per day
        period_data = price_series.iloc[-data_points:] if len(price_series) >= data_points else price_series
        avg_price = period_data.mean()
        
        raw_mining = sum([max(0, breakeven_val - p) * ideal_m for p in period_data]) / 288.0
        raw_battery = sum([max(0, p - breakeven_val) * ideal_b for p in period_data]) / 288.0
        
        weighted_mining = raw_mining * (1.0 + (w_pct * 0.20))
        weighted_battery = raw_battery * (1.0 + (s_pct * 0.25))
        
        return weighted_mining, weighted_battery, avg_price
    except: return 0, 0, 0

# --- 5. DASHBOARD INTERFACE ---
t_baseload, t_evolution, t_tax, t_volatility, t_price_dsets = st.tabs([
    "🏭 Thermal Baseload OS", "📊 Renewable Evolution", "🏛️ Institutional Tax Strategy", "📈 Long-Term Volatility", "📊 Price Datasets"
])

# ==========================================
# THERMAL BASELOAD OS (HARDIN, MT)
# ==========================================
with t_baseload:
    st.markdown("### 🏭 100 MW Thermal Baseload Optimization (Hardin, MT)")
    st.write("Optimizing a 'Must-Run' thermal asset requires a synthetic floor to mitigate losses during negative pricing, and a peak multiplier (BESS) to capitalize on extreme summer scarcity.")
    
    coal_mw = 100
    coal_cost_mwh = 55.00
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Nameplate Capacity", f"{coal_mw} MW", "Must-Run")
    c2.metric("Production Cost", f"${coal_cost_mwh:.2f}/MWh", "- Fixed Sunk Cost", delta_color="inverse")
    c3.metric("Miner Breakeven", f"${breakeven:.2f}/MWh", "Synthetic Floor")
    c4.metric("Current Market Price", f"${price_hist.iloc[-1] if len(price_hist) > 0 else 0:.2f}/MWh")
    
    st.markdown("---")
    st.subheader("⚙️ Recommended Hardware Sizing & Tax Subsidies")
    
    base_itc = 0.30
    energy_community_bonus = 0.10
    domestic_content = 0.10
    total_itc = base_itc + energy_community_bonus + domestic_content
    
    ideal_coal_miners = coal_mw
    ideal_coal_battery = int(coal_mw * 0.25)
    
    b1, b2 = st.columns([1, 1.5])
    with b1:
        st.markdown(f"**Optimal Miners:** `{ideal_coal_miners} MW`")
        st.write("*Rationale:* Matches nameplate exactly. Ensures the plant never sells power to the grid for less than the Miner Breakeven.")
        st.markdown(f"**Optimal Battery:** `{ideal_coal_battery} MW`")
        st.write("*Rationale:* Sized to discharge during extreme summer peaks, allowing the site to export 125% of its nameplate capacity.")
    with b2:
        st.markdown("**Tax Shield Impact (Hardin, MT)**")
        st.info(f"📍 **Location Bonus:** Hardin qualifies as an 'Energy Community' (coal transition zone), unlocking a 10% ITC bonus.")
        st.write(f"- Base ITC: {base_itc*100}%\n- Energy Community Bonus: {energy_community_bonus*100}%\n- Domestic Content: {domestic_content*100}%")
        st.markdown(f"**Total Battery Capex Covered by ITC: <span style='color:#28a745; font-size:20px;'>{total_itc*100}%</span>**", unsafe_allow_html=True)
    
    st.markdown("---")
    st.subheader("🔄 Automated Routing Logic Matrix")
    
    logic_df = pd.DataFrame({
        "Grid Price State": [f"Deep Discount (Price < ${breakeven:.0f})", f"Loss Mitigation (${breakeven:.0f} - ${coal_cost_mwh:.0f})", f"Profit Export (Price > ${coal_cost_mwh:.0f})", "Summer Peak Scarcity (Price > $150)"],
        "Miner Status": ["100 MW ACTIVE", "OFF", "OFF", "OFF"],
        "Battery Status": ["CHARGING (Using Miner Opp. Cost)", "IDLE", "IDLE", "DISCHARGING 25 MW"],
        "Grid Export": ["0 MW", "100 MW", "100 MW", "125 MW (Peak Multiplier)"],
        "Net Financial Result": ["Synthetic Floor Achieved", "Loss Minimized", "Pure Profit", "Maximized Alpha"]
    })
    st.table(logic_df.set_index("Grid Price State"))

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
    st.write("The volatility of grid operators varies significantly across North America. This analysis compares pricing distribution patterns across major ISOs, identifying arbitrage opportunities and regional risk profiles.")
    
    st.markdown("#### 1. The Lower Bound: Exponential Growth of Negative Pricing")
    st.write("The lower pricing bound is increasingly defined by 'excess supply' events, where the grid has more power than it can consume or export.")
    st.write("* **Solar Saturation:** As solar capacity grows, the frequency of prices in the $0 - $0.02/kWh bracket has transitioned from a localized West Texas issue to a system-wide phenomenon.")
    
    st.markdown("#### 2. The Upper Bound: Scarcity and Peak Pricing")
    st.write("The upper bound is becoming more volatile due to 'scarcity' events when renewable generation drops off just as demand peaks.")
    st.write("* **Battery Dominance:** This volatility at the top is the primary revenue driver for the **Battery Alpha**, as the battery only discharges during scarcity windows.")

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
    st.markdown("### Explore Historical and 24-Hour Live-Time Price Data")
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
