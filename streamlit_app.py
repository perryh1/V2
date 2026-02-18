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

# --- 2. MOBILE-FRIENDLY AUTHENTICATION PORTAL ---
if "password_correct" not in st.session_state: 
    st.session_state.password_correct = False

def check_password():
    if st.session_state.password_correct: return True
    
    # CSS for Responsive Flexbox Layout and Branding
    st.markdown("""
        <style>
        .stApp { background-color: #0e1117; }
        
        /* Container that stacks on mobile, side-by-side on desktop */
        .flex-container {
            display: flex;
            flex-wrap: wrap;
            min-height: 100vh;
            width: 100%;
        }
        
        .login-sidebar {
            background-color: #262730;
            flex: 1 1 300px;
            padding: 40px;
            color: white;
            border-right: 1px solid #3d3f4b;
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
        }
        
        .login-main {
            flex: 3 1 400px;
            padding: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .brand-text { color: #ffffff; font-family: 'Inter', sans-serif; font-weight: 800; font-size: 32px; margin-bottom: 5px; }
        .version-text { color: #808495; font-size: 14px; margin-bottom: 40px; }
        
        .auth-card {
            background: #161b22;
            padding: 30px;
            border-radius: 8px;
            border: 1px solid #30363d;
            width: 100%;
            max-width: 500px;
        }
        
        .auth-header { color: #ffffff; font-weight: 700; font-size: 24px; margin-bottom: 8px; }
        .auth-sub { color: #8b949e; font-size: 14px; margin-bottom: 24px; }
        
        .brief-section { color: #c9d1d9; font-size: 14px; line-height: 1.6; margin-bottom: 30px; border-left: 2px solid #0052FF; padding-left: 15px; }
        .brief-title { color: #58a6ff; font-weight: 600; font-size: 12px; text-transform: uppercase; margin-bottom: 10px; letter-spacing: 1px; }

        /* Mobile Adjustments */
        @media (max-width: 768px) {
            .login-sidebar { min-height: auto; border-right: none; border-bottom: 1px solid #3d3f4b; }
            .login-main { padding: 20px; }
        }
        </style>
    """, unsafe_allow_html=True)

    # Building the responsive structure
    st.markdown('<div class="flex-container">', unsafe_allow_html=True)
    
    # Left/Top Section (Branding)
    st.markdown(f'''
        <div class="login-sidebar">
            <p class="brand-text">Hybrid OS</p>
            <p class="version-text">v13.2 Deployment</p>
        </div>
    ''', unsafe_allow_html=True)
    
    # Right/Bottom Section (Auth & Brief)
    st.markdown('<div class="login-main"><div class="auth-card">', unsafe_allow_html=True)
    st.markdown('<p class="auth-header">Executive Access</p>', unsafe_allow_html=True)
    st.markdown('<p class="auth-sub">Grid Intelligence & Asset Optimization Portal</p>', unsafe_allow_html=True)
    
    st.markdown('<p class="brief-title">Strategic Value Proposition</p>', unsafe_allow_html=True)
    st.markdown("""
    <div class="brief-section">
        • <b>Dynamic Arbitrage:</b> Automatically identifies high-alpha windows where compute load 
        at 15 J/TH outperforms spot market grid exports.<br><br>
        • <b>Yield Optimization:</b> Mathematically ideal BESS-to-Compute ratios 
        calibrated to local volatility and generation sources.<br><br>
        • <b>Financial Engineering:</b> Integrated ITC and MACRS tax shields for 
        institutional IRR and Payback projections.
    </div>
    """, unsafe_allow_html=True)
    
    pwd = st.text_input("Institutional Access Key", type="password")
    if st.button("Authenticate Session", use_container_width=True, type="primary"):
        if pwd == DASHBOARD_PASSWORD:
            st.session_state.password_correct = True
            st.rerun()
        else:
            st.error("Authentication Failed")
            
    st.markdown('</div></div></div>', unsafe_allow_html=True)
    return False

if not check_password(): st.stop()

# --- 3. PERSISTENT SIDEBAR CONTROLS ---
st.sidebar.markdown("# Hybrid OS")
st.sidebar.caption("v13.2 Deployment")
st.sidebar.write("---")

st.sidebar.markdown("### ⚡ Generation Mix")
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

# --- 4. DATASETS & CALCS (Logic remains as Version 13.1) ---
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

@st.cache_data(ttl=300)
def get_live_data():
    try:
        iso = gridstatus.Ercot()
        df = iso.get_rtm_lmp(start=pd.Timestamp.now(tz="US/Central")-pd.Timedelta(days=31), end=pd.Timestamp.now(tz="US/Central"), verbose=False)
        return df[df['Location'] == 'HB_WEST'].set_index('Time').sort_index()['LMP']
    except: return pd.Series(np.random.uniform(15, 45, 744))

price_hist = get_live_data()
breakeven = (1e6 / m_eff) * (hp_cents / 100.0) / 24.0

# --- 5. DASHBOARD MAIN INTERFACE ---
t_evolution, t_tax, t_volatility = st.tabs(["📊 Performance Evolution", "🏛️ Institutional Tax Strategy", "📈 Long-Term Volatility"])
# [Remaining Dashboard code from 13.1...]
