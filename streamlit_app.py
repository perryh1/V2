import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="West Texas Energy Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background: #0a0e1a; color: #e2e8f0; }
    .ticker-bar {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 18px 28px;
        display: flex;
        align-items: center;
        gap: 24px;
        margin-bottom: 8px;
        box-shadow: 0 4px 24px rgba(0,0,0,0.4);
    }
    .ticker-label { font-size:11px; font-weight:600; letter-spacing:2px; text-transform:uppercase; color:#64748b; }
    .ticker-price-pos { font-size:48px; font-weight:900; color:#10b981; line-height:1; }
    .ticker-price-neg { font-size:48px; font-weight:900; color:#ef4444; line-height:1; }
    .ticker-badge-pos { background:rgba(16,185,129,0.15); color:#10b981; border:1px solid #10b981; border-radius:6px; padding:4px 12px; font-size:13px; font-weight:600; }
    .ticker-badge-neg { background:rgba(239,68,68,0.15); color:#ef4444; border:1px solid #ef4444; border-radius:6px; padding:4px 12px; font-size:13px; font-weight:600; }
    .rev-card {
        background: linear-gradient(135deg, #0f172a 0%, #1a2540 100%);
        border: 1px solid #334155;
        border-radius: 14px;
        padding: 24px;
        box-shadow: 0 4px 24px rgba(0,0,0,0.35);
        margin-bottom: 8px;
    }
    .rev-card-winner {
        background: linear-gradient(135deg, #0c1f14 0%, #0f2a1e 100%);
        border: 1px solid #059669;
        border-radius: 14px;
        padding: 24px;
        box-shadow: 0 4px 32px rgba(5,150,105,0.2);
        margin-bottom: 8px;
    }
    .card-title { font-size:11px; font-weight:700; letter-spacing:2px; text-transform:uppercase; color:#64748b; margin-bottom:4px; }
    .card-subtitle { font-size:12px; color:#475569; margin-bottom:14px; }
    .card-revenue { font-size:36px; font-weight:900; color:#f1f5f9; line-height:1; margin-bottom:4px; }
    .card-revenue-green { font-size:36px; font-weight:900; color:#10b981; line-height:1; margin-bottom:4px; }
    .card-unit { font-size:13px; color:#64748b; margin-bottom:14px; }
    .card-delta-pos { background:rgba(16,185,129,0.12); color:#10b981; border-radius:8px; padding:8px 14px; font-size:14px; font-weight:700; display:inline-block; margin-top:8px; }
    .card-delta-neg { background:rgba(239,68,68,0.12); color:#ef4444; border-radius:8px; padding:8px 14px; font-size:14px; font-weight:700; display:inline-block; margin-top:8px; }
    .state-badge { background:rgba(59,130,246,0.15); color:#60a5fa; border:1px solid #3b82f6; border-radius:6px; padding:5px 12px; font-size:11px; font-weight:700; letter-spacing:1px; display:inline-block; margin-top:10px; }
    .state-badge-neg { background:rgba(239,68,68,0.15); color:#ef4444; border:1px solid #ef4444; border-radius:6px; padding:5px 12px; font-size:11px; font-weight:700; display:inline-block; margin-top:10px; }
    .state-badge-mine { background:rgba(251,191,36,0.15); color:#fbbf24; border:1px solid #fbbf24; border-radius:6px; padding:5px 12px; font-size:11px; font-weight:700; display:inline-block; margin-top:10px; }
    .state-badge-grid { background:rgba(16,185,129,0.15); color:#10b981; border:1px solid #10b981; border-radius:6px; padding:5px 12px; font-size:11px; font-weight:700; display:inline-block; margin-top:10px; }
    .section-header { font-size:11px; font-weight:700; letter-spacing:3px; text-transform:uppercase; color:#475569; padding:20px 0 8px 0; border-bottom:1px solid #1e293b; margin-bottom:16px; }
    .info-pill { background:#1e293b; border:1px solid #334155; border-radius:8px; padding:10px 16px; font-size:12px; color:#94a3b8; display:inline-block; margin:4px; }
    .info-pill strong { color:#e2e8f0; }
    #MainMenu { visibility:hidden; }
    footer { visibility:hidden; }
    header { visibility:hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

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
PASSWORD = "Hardin2026"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def login_page():
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(
            """
            <div style="text-align:center; background:#0f172a; border:1px solid #334155;
            border-radius:16px; padding:40px; box-shadow:0 20px 60px rgba(0,0,0,0.5);">
            <div style="font-size:40px; margin-bottom:12px;">⚡</div>
            <div style="font-size:22px; font-weight:800; color:#f1f5f9;">West Texas Energy</div>
            <div style="font-size:13px; color:#64748b; margin-top:6px; letter-spacing:1px;">
            100 MW RENEWABLE PORTFOLIO DASHBOARD
            </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)
        pwd = st.text_input("Password", type="password", placeholder="Enter dashboard password")
        if st.button("Login", use_container_width=True, type="primary"):
            if pwd == PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Invalid password.")

if not st.session_state.authenticated:
    login_page()
    st.stop()

@st.cache_data(ttl=300)
def get_ercot_price():
    try:
        import gridstatus
        iso = gridstatus.Ercot()
        df = iso.get_lmp(date="latest", market="REAL_TIME_15_MIN", locations=["HB_WEST"])
        if df is not None and not df.empty:
            price_col = None
            for col in ["LMP", "lmp", "Price", "price", "SPP", "spp"]:
                if col in df.columns:
                    price_col = col
                    break
            if price_col is None:
                numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                if numeric_cols:
                    price_col = numeric_cols[0]
            if price_col:
                latest = df.iloc[-1]
                price = float(latest[price_col])
                ts_col = next((c for c in ["Time", "time", "Interval Start", "interval_start", "timestamp"] if c in df.columns), None)
                ts = str(latest[ts_col]) if ts_col else datetime.now().strftime("%Y-%m-%d %H:%M")
                return {"price": price, "timestamp": ts, "source": "ERCOT Live (gridstatus)"}
    except Exception:
        pass
    now = datetime.utcnow()
    bucket = now.hour * 12 + now.minute // 5
    base = 35.0
    diurnal = (25.0 * np.sin(2 * np.pi * (bucket - 40) / 288) + 15.0 * np.sin(2 * np.pi * (bucket - 200) / 288))
    rng = np.random.default_rng(bucket)
    noise = float(rng.normal(0, 6))
    price = round(base + diurnal + noise, 2)
    return {"price": price, "timestamp": now.strftime("%Y-%m-%d %H:%M UTC"), "source": "Simulated (gridstatus unavailable)"}

@st.cache_data(ttl=300)
def get_weather():
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={MIDLAND_LAT}&longitude={MIDLAND_LON}"
        f"&current=temperature_2m,wind_speed_10m,shortwave_radiation"
        f"&wind_speed_unit=mph&timezone=America%2FChicago"
    )
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        current = data.get("current", {})
        return {
            "temperature_f": round(current.get("temperature_2m", 85) * 9 / 5 + 32, 1),
            "wind_mph": round(current.get("wind_speed_10m", 12), 1),
            "solar_w_m2": round(current.get("shortwave_radiation", 400), 1),
            "source": "Open-Meteo (live)",
        }
    except Exception as e:
        return {"temperature_f": 95.0, "wind_mph": 14.0, "solar_w_m2": 550.0, "source": f"Simulated ({e})"}

@st.cache_data(ttl=300)
def get_weather_history():
    now = datetime.utcnow()
    start = (now - timedelta(hours=24)).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={MIDLAND_LAT}&longitude={MIDLAND_LON}"
        f"&hourly=temperature_2m,wind_speed_10m,shortwave_radiation"
        f"&start_date={start}&end_date={end}"
        f"&wind_speed_unit=mph&timezone=America%2FChicago"
    )
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        hourly = data.get("hourly", {})
        df = pd.DataFrame({
            "time": pd.to_datetime(hourly.get("time", [])),
            "wind_mph": hourly.get("wind_speed_10m", []),
            "solar": hourly.get("shortwave_radiation", []),
        })
        return df
    except Exception:
        hours = pd.date_range(end=datetime.utcnow(), periods=24, freq="h")
        return pd.DataFrame({
            "time": hours,
            "wind_mph": np.random.uniform(8, 20, 24),
            "solar": np.clip(np.sin(np.linspace(0, np.pi, 24)) * 700, 0, None),
        })

def calc_solar_output(solar_w_m2):
    cf = min(solar_w_m2 / 1000.0, 1.0) * 0.85
    return round(SOLAR_CAP_MW * cf, 2)

def calc_wind_output(wind_mph):
    if wind_mph < 7 or wind_mph > 55:
        cf = 0.0
    elif wind_mph >= 30:
        cf = 1.0
    else:
        cf = ((wind_mph - 7) / 23) ** 3 * 0.92
    return round(WIND_CAP_MW * cf, 2)

def smart_dispatch(total_gen_mw, price):
    mining_rev_hr = MINER_MW * MINING_REV_MWH
    if price < 0:
        battery_rev = abs(price) * BATTERY_MW
        total_rev = battery_rev + mining_rev_hr
        state = "CHARGE + MINE"
        badge_class = "state-badge-neg"
        breakdown = {
            "Neg-Price Battery Arbitrage": battery_rev,
            "Mining Revenue": mining_rev_hr,
            "Grid Sales": 0.0,
        }
    elif price <= MINING_REV_MWH:
        grid_gen = max(total_gen_mw - MINER_MW, 0.0)
        grid_rev = grid_gen * price
        total_rev = mining_rev_hr + grid_rev
        state = "MINE + GRID SELL"
        badge_class = "state-badge-mine"
        breakdown = {
            "Mining Revenue": mining_rev_hr,
            "Excess Renewable Sales": grid_rev,
            "Battery Discharge": 0.0,
        }
    else:
        grid_gen = total_gen_mw + BATTERY_MW
        total_rev = grid_gen * price
        state = "FULL GRID DISPATCH"
        badge_class = "state-badge-grid"
        breakdown = {
            "Renewable Grid Sales": total_gen_mw * price,
            "Battery Discharge Rev": BATTERY_MW * price,
            "Mining Revenue": 0.0,
        }
    return {
        "revenue_hr": round(total_rev, 2),
        "state": state,
        "badge_class": badge_class,
        "breakdown": breakdown,
    }

def fmt(val, decimals=0):
    if val >= 0:
        return f"${val:,.{decimals}f}"
    return f"-${abs(val):,.{decimals}f}"

def make_gauge(value, max_val, title, unit, color):
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            title={"text": f"<b>{title}</b>", "font": {"size": 12, "color": "#94a3b8"}},
            number={"suffix": f" {unit}", "font": {"size": 24, "color": "#f1f5f9"}},
            gauge={
                "axis": {"range": [0, max_val], "tickcolor": "#475569", "tickfont": {"size": 9, "color": "#475569"}, "nticks": 5},
                "bar": {"color": color, "thickness": 0.28},
                "bgcolor": "#0f172a",
                "bordercolor": "#334155",
                "steps": [
                    {"range": [0, max_val * 0.33], "color": "#1e293b"},
                    {"range": [max_val * 0.33, max_val * 0.67], "color": "#1a2540"},
                    {"range": [max_val * 0.67, max_val], "color": "#162035"},
                ],
            },
        )
    )
    fig.update_layout(paper_bgcolor="#0a0e1a", plot_bgcolor="#0a0e1a", margin=dict(l=20, r=20, t=55, b=10), height=195)
    return fig

def main():
    price_data = get_ercot_price()
    weather = get_weather()
    hist_df = get_weather_history()
    price = price_data["price"]
    solar_mw = calc_solar_output(weather["solar_w_m2"])
    wind_mw = calc_wind_output(weather["wind_mph"])
    total_gen = solar_mw + wind_mw
    rev_a_hr = total_gen * price
    rev_b_hr = MINER_MW * MINING_REV_MWH
    hybrid = smart_dispatch(total_gen, price)
    rev_c_hr = hybrid["revenue_hr"]
    delta_hr = rev_c_hr - rev_a_hr

    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:14px; margin-bottom:6px;">
            <span style="font-size:32px;">⚡</span>
            <div>
                <div style="font-size:24px; font-weight:800; color:#f1f5f9; line-height:1.1;">
                    West Texas Renewable Portfolio
                </div>
                <div style="font-size:11px; color:#64748b; letter-spacing:2px; margin-top:3px;">
                    100 MW SOLAR - 100 MW WIND - 35 MW BITCOIN MINERS - 60 MW / 120 MWh BATTERY - ERCOT WEST HUB
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Rest of your rendering logic goes here inside main()...
    st.write(f"Current Price: {fmt(price, 2)}")
    st.write(f"Hybrid Strategy: {hybrid['state']}")

if __name__ == "__main__":
    main()
