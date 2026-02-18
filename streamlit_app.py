import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta
import warnings
from concurrent.futures import ThreadPoolExecutor

# 1. SETUP & CONFIG
warnings.filterwarnings("ignore")
st.set_page_config(
    page_title="West Texas Energy Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Constants
SOLAR_CAP_MW = 100.0
WIND_CAP_MW = 100.0
MINER_MW = 35.0
BATTERY_MW = 60.0
BATTERY_MWH = 120.0
HASHPRICE = 0.04
EFFICIENCY_J_TH = 19.0
MINING_REV_MWH = (0.04 / (19 * 1e-6 * 24 * 3600)) * 1e6
MIDLAND_LAT = 32.0
MIDLAND_LON = -102.1
PASSWORD = "123"

# 2. STYLING
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background: #0a0e1a; color: #e2e8f0; }
    .ticker-bar {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        border: 1px solid #334155; border-radius: 12px; padding: 18px 28px;
        display: flex; align-items: center; gap: 24px; margin-bottom: 8px;
        box-shadow: 0 4px 24px rgba(0,0,0,0.4);
    }
    .ticker-label { font-size:11px; font-weight:600; letter-spacing:2px; text-transform:uppercase; color:#64748b; }
    .ticker-price-pos { font-size:48px; font-weight:900; color:#10b981; line-height:1; }
    .ticker-price-neg { font-size:48px; font-weight:900; color:#ef4444; line-height:1; }
    .ticker-badge-pos { background:rgba(16,185,129,0.15); color:#10b981; border:1px solid #10b981; border-radius:6px; padding:4px 12px; font-size:13px; font-weight:600; }
    .ticker-badge-neg { background:rgba(239,68,68,0.15); color:#ef4444; border:1px solid #ef4444; border-radius:6px; padding:4px 12px; font-size:13px; font-weight:600; }
    .rev-card {
        background: linear-gradient(135deg, #0f172a 0%, #1a2540 100%);
        border: 1px solid #334155; border-radius: 14px; padding: 24px; margin-bottom: 8px;
    }
    .rev-card-winner {
        background: linear-gradient(135deg, #0c1f14 0%, #0f2a1e 100%);
        border: 1px solid #059669; border-radius: 14px; padding: 24px;
        box-shadow: 0 4px 32px rgba(5,150,105,0.2); margin-bottom: 8px;
    }
    .card-revenue-green { font-size:36px; font-weight:900; color:#10b981; line-height:1; }
    .section-header { font-size:11px; font-weight:700; letter-spacing:3px; text-transform:uppercase; color:#475569; padding:20px 0 8px 0; border-bottom:1px solid #1e293b; margin-bottom:16px; }
    .info-pill { background:#1e293b; border:1px solid #334155; border-radius:8px; padding:10px 16px; font-size:12px; color:#94a3b8; display:inline-block; margin:4px; }
    .card-delta-pos { background:rgba(16,185,129,0.12); color:#10b981; border-radius:8px; padding:8px 14px; font-size:14px; font-weight:700; display:inline-block; margin-top:8px; }
    .card-delta-neg { background:rgba(239,68,68,0.12); color:#ef4444; border-radius:8px; padding:8px 14px; font-size:14px; font-weight:700; display:inline-block; margin-top:8px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# 3. CORE LOGIC & DATA FETCHING
@st.cache_data(ttl=300)
def get_ercot_price():
    try:
        import gridstatus
        iso = gridstatus.Ercot()
        df = iso.get_lmp(date="latest", market="REAL_TIME_15_MIN", locations=["HB_WEST"])
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            price = float(latest.get("LMP", latest.get("Price", 35.0)))
            return {"price": price, "timestamp": str(datetime.now().strftime("%H:%M")), "source": "ERCOT Live"}
    except Exception:
        pass
    return {"price": 42.50, "timestamp": "Simulated", "source": "Fallback"}

@st.cache_data(ttl=300)
def get_weather_data():
    url = f"https://api.open-meteo.com/v1/forecast?latitude={MIDLAND_LAT}&longitude={MIDLAND_LON}&current=temperature_2m,wind_speed_10m,shortwave_radiation&wind_speed_unit=mph&timezone=America%2FChicago"
    try:
        r = requests.get(url, timeout=5).json()
        curr = r["current"]
        return {
            "temp": curr["temperature_2m"] * 9/5 + 32,
            "wind": curr["wind_speed_10m"],
            "solar": curr["shortwave_radiation"]
        }
    except:
        return {"temp": 85, "wind": 12, "solar": 400}

def smart_dispatch(total_gen_mw, price):
    mining_rev_hr = MINER_MW * MINING_REV_MWH
    if price < 0:
        return {"revenue_hr": (abs(price) * BATTERY_MW) + mining_rev_hr, "state": "CHARGE + MINE", "class": "ticker-badge-neg"}
    elif price <= MINING_REV_MWH:
        return {"revenue_hr": mining_rev_hr + (max(total_gen_mw - MINER_MW, 0) * price), "state": "MINE + GRID SELL", "class": "state-badge-mine"}
    else:
        return {"revenue_hr": (total_gen_mw + BATTERY_MW) * price, "state": "FULL GRID DISPATCH", "class": "state-badge-grid"}

def make_gauge(value, max_val, title, color):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value,
        title={'text': title, 'font': {'size': 14, 'color': '#94a3b8'}},
        gauge={'axis': {'range': [0, max_val]}, 'bar': {'color': color}}
    ))
    fig.update_layout(paper_bgcolor="#0a0e1a", plot_bgcolor="#0a0e1a", height=180, margin=dict(l=20,r=20,t=40,b=20))
    return fig

# 4. AUTHENTICATION
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<br><br><h2 style='text-align:center;'>West Texas Portfolio Login</h2>", unsafe_allow_html=True)
    pwd = st.text_input("Enter Dashboard Password", type="password")
    if st.button("Access Dashboard", use_container_width=True):
        if pwd == PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Invalid Credentials")
    st.stop()

# 5. MAIN DASHBOARD RENDER
def main():
    # Fast Parallel Data Fetching
    with ThreadPoolExecutor() as executor:
        price_future = executor.submit(get_ercot_price)
        weather_future = executor.submit(get_weather_data)
        price_data = price_future.result()
        weather = weather_future.result()

    price = price_data["price"]
    solar_mw = round(SOLAR_CAP_MW * (min(weather["solar"] / 1000, 1) * 0.85), 2)
    wind_mw = round(WIND_CAP_MW * (((weather["wind"]-7)/23)**3 * 0.92 if 7 < weather["wind"] < 30 else (1.0 if weather["wind"]>=30 else 0)), 2)
    
    total_gen = solar_mw + wind_mw
    hybrid = smart_dispatch(total_gen, price)
    
    # Header
    st.markdown(f"""
        <div class="ticker-bar">
            <div>
                <div class="ticker-label">ERCOT West Hub LMP</div>
                <div class="{'ticker-price-neg' if price < 0 else 'ticker-price-pos'}">${price:,.2f}<span style="font-size:18px;">/MWh</span></div>
            </div>
            <div style="margin-left:auto;">
                <div class="ticker-badge-pos">{hybrid['state']}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Asset Gauges
    st.markdown('<div class="section-header">LIVE ASSET STATUS</div>', unsafe_allow_html=True)
    g1, g2, g3, g4 = st.columns(4)
    g1.plotly_chart(make_gauge(solar_mw, SOLAR_CAP_MW, "Solar MW", "#f59e0b"), use_container_width=True)
    g2.plotly_chart(make_gauge(wind_mw, WIND_CAP_MW, "Wind MW", "#3b82f6"), use_container_width=True)
    g3.plotly_chart(make_gauge(MINER_MW if price < MINING_REV_MWH else 0, MINER_MW, "Miner Load", "#8b5cf6"), use_container_width=True)
    g4.plotly_chart(make_gauge(50, 100, "Battery SOC %", "#06b6d4"), use_container_width=True)

    # Revenue Cards
    st.markdown('<div class="section-header">STRATEGY COMPARISON</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown(f"""<div class="rev-card"><h3>Grid Only</h3><h2 style="color:#3b82f6;">${(total_gen * price):,.2f}/hr</h2></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="rev-card"><h3>Mining Only</h3><h2 style="color:#8b5cf6;">${(MINER_MW * MINING_REV_MWH):,.2f}/hr</h2></div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="rev-card-winner"><h3>Hybrid Optimal</h3><h2 class="card-revenue-green">${hybrid['revenue_hr']:,.2f}/hr</h2></div>""", unsafe_allow_html=True)

    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.rerun()

if __name__ == "__main__":
    main()
