“””
Real-Time Financial Dashboard for 100 MW Renewable Energy Portfolio
West Texas ERCOT West Hub
“””

import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings(“ignore”)

st.set_page_config(
page_title=“West Texas Energy Dashboard”,
page_icon=“⚡”,
layout=“wide”,
initial_sidebar_state=“collapsed”,
)

st.markdown(
“””
<style>
@import url(‘https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&display=swap’);
html, body, [class*=“css”] { font-family: ‘Inter’, sans-serif; }
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
“””,
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
PASSWORD = “Hardin2026”

if “authenticated” not in st.session_state:
st.session_state.authenticated = False

def login_page():
col1, col2, col3 = st.columns([1, 1.2, 1])
with col2:
st.markdown(”<br><br>”, unsafe_allow_html=True)
st.markdown(
“””
<div style="text-align:center; background:#0f172a; border:1px solid #334155;
border-radius:16px; padding:40px; box-shadow:0 20px 60px rgba(0,0,0,0.5);">
<div style="font-size:40px; margin-bottom:12px;">⚡</div>
<div style="font-size:22px; font-weight:800; color:#f1f5f9;">West Texas Energy</div>
<div style="font-size:13px; color:#64748b; margin-top:6px; letter-spacing:1px;">
100 MW RENEWABLE PORTFOLIO DASHBOARD
</div>
</div>
“””,
unsafe_allow_html=True,
)
st.markdown(”<br>”, unsafe_allow_html=True)
pwd = st.text_input(“Password”, type=“password”, placeholder=“Enter dashboard password”)
if st.button(“Login”, use_container_width=True, type=“primary”):
if pwd == PASSWORD:
st.session_state.authenticated = True
st.rerun()
else:
st.error(“Invalid password.”)

if not st.session_state.authenticated:
login_page()
st.stop()

@st.cache_data(ttl=300)
def get_ercot_price():
try:
import gridstatus
iso = gridstatus.Ercot()
df = iso.get_lmp(date=“latest”, market=“REAL_TIME_15_MIN”, locations=[“HB_WEST”])
if df is not None and not df.empty:
price_col = None
for col in [“LMP”, “lmp”, “Price”, “price”, “SPP”, “spp”]:
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
ts_col = next((c for c in [“Time”, “time”, “Interval Start”, “interval_start”, “timestamp”] if c in df.columns), None)
ts = str(latest[ts_col]) if ts_col else datetime.now().strftime(”%Y-%m-%d %H:%M”)
return {“price”: price, “timestamp”: ts, “source”: “ERCOT Live (gridstatus)”}
except Exception:
pass
now = datetime.utcnow()
bucket = now.hour * 12 + now.minute // 5
base = 35.0
diurnal = (25.0 * np.sin(2 * np.pi * (bucket - 40) / 288) + 15.0 * np.sin(2 * np.pi * (bucket - 200) / 288))
rng = np.random.default_rng(bucket)
noise = float(rng.normal(0, 6))
price = round(base + diurnal + noise, 2)
return {“price”: price, “timestamp”: now.strftime(”%Y-%m-%d %H:%M UTC”), “source”: “Simulated (gridstatus unavailable)”}

@st.cache_data(ttl=300)
def get_weather():
url = (
f”https://api.open-meteo.com/v1/forecast”
f”?latitude={MIDLAND_LAT}&longitude={MIDLAND_LON}”
f”&current=temperature_2m,wind_speed_10m,shortwave_radiation”
f”&wind_speed_unit=mph&timezone=America%2FChicago”
)
try:
r = requests.get(url, timeout=10)
r.raise_for_status()
data = r.json()
current = data.get(“current”, {})
return {
“temperature_f”: round(current.get(“temperature_2m”, 85) * 9 / 5 + 32, 1),
“wind_mph”: round(current.get(“wind_speed_10m”, 12), 1),
“solar_w_m2”: round(current.get(“shortwave_radiation”, 400), 1),
“source”: “Open-Meteo (live)”,
}
except Exception as e:
return {“temperature_f”: 95.0, “wind_mph”: 14.0, “solar_w_m2”: 550.0, “source”: f”Simulated ({e})”}

@st.cache_data(ttl=300)
def get_weather_history():
now = datetime.utcnow()
start = (now - timedelta(hours=24)).strftime(”%Y-%m-%d”)
end = now.strftime(”%Y-%m-%d”)
url = (
f”https://api.open-meteo.com/v1/forecast”
f”?latitude={MIDLAND_LAT}&longitude={MIDLAND_LON}”
f”&hourly=temperature_2m,wind_speed_10m,shortwave_radiation”
f”&start_date={start}&end_date={end}”
f”&wind_speed_unit=mph&timezone=America%2FChicago”
)
try:
r = requests.get(url, timeout=10)
r.raise_for_status()
data = r.json()
hourly = data.get(“hourly”, {})
df = pd.DataFrame({
“time”: pd.to_datetime(hourly.get(“time”, [])),
“wind_mph”: hourly.get(“wind_speed_10m”, []),
“solar”: hourly.get(“shortwave_radiation”, []),
})
return df
except Exception:
hours = pd.date_range(end=datetime.utcnow(), periods=24, freq=“h”)
return pd.DataFrame({
“time”: hours,
“wind_mph”: np.random.uniform(8, 20, 24),
“solar”: np.clip(np.sin(np.linspace(0, np.pi, 24)) * 700, 0, None),
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
state = “CHARGE + MINE”
badge_class = “state-badge-neg”
breakdown = {
“Neg-Price Battery Arbitrage”: battery_rev,
“Mining Revenue”: mining_rev_hr,
“Grid Sales”: 0.0,
}
elif price <= MINING_REV_MWH:
grid_gen = max(total_gen_mw - MINER_MW, 0.0)
grid_rev = grid_gen * price
total_rev = mining_rev_hr + grid_rev
state = “MINE + GRID SELL”
badge_class = “state-badge-mine”
breakdown = {
“Mining Revenue”: mining_rev_hr,
“Excess Renewable Sales”: grid_rev,
“Battery Discharge”: 0.0,
}
else:
grid_gen = total_gen_mw + BATTERY_MW
total_rev = grid_gen * price
state = “FULL GRID DISPATCH”
badge_class = “state-badge-grid”
breakdown = {
“Renewable Grid Sales”: total_gen_mw * price,
“Battery Discharge Rev”: BATTERY_MW * price,
“Mining Revenue”: 0.0,
}
return {
“revenue_hr”: round(total_rev, 2),
“state”: state,
“badge_class”: badge_class,
“breakdown”: breakdown,
}

def fmt(val, decimals=0):
if val >= 0:
return f”${val:,.{decimals}f}”
return f”-${abs(val):,.{decimals}f}”

def make_gauge(value, max_val, title, unit, color):
fig = go.Figure(
go.Indicator(
mode=“gauge+number”,
value=value,
title={“text”: f”<b>{title}</b>”, “font”: {“size”: 12, “color”: “#94a3b8”}},
number={“suffix”: f” {unit}”, “font”: {“size”: 24, “color”: “#f1f5f9”}},
gauge={
“axis”: {“range”: [0, max_val], “tickcolor”: “#475569”, “tickfont”: {“size”: 9, “color”: “#475569”}, “nticks”: 5},
“bar”: {“color”: color, “thickness”: 0.28},
“bgcolor”: “#0f172a”,
“bordercolor”: “#334155”,
“steps”: [
{“range”: [0, max_val * 0.33], “color”: “#1e293b”},
{“range”: [max_val * 0.33, max_val * 0.67], “color”: “#1a2540”},
{“range”: [max_val * 0.67, max_val], “color”: “#162035”},
],
},
)
)
fig.update_layout(paper_bgcolor=”#0a0e1a”, plot_bgcolor=”#0a0e1a”, margin=dict(l=20, r=20, t=55, b=10), height=195)
return fig

def main():
price_data = get_ercot_price()
weather = get_weather()
hist_df = get_weather_history()
price = price_data[“price”]
solar_mw = calc_solar_output(weather[“solar_w_m2”])
wind_mw = calc_wind_output(weather[“wind_mph”])
total_gen = solar_mw + wind_mw
rev_a_hr = total_gen * price
rev_b_hr = MINER_MW * MINING_REV_MWH
hybrid = smart_dispatch(total_gen, price)
rev_c_hr = hybrid[“revenue_hr”]
delta_hr = rev_c_hr - rev_a_hr

```
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
        <div style="margin-left:auto; text-align:right;">
            <div style="font-size:9px; color:#334155; letter-spacing:1px; text-transform:uppercase;">Last Refresh</div>
            <div style="font-size:13px; color:#94a3b8; font-weight:600;">
                {datetime.now().strftime("%b %d, %Y  %H:%M:%S")}
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

price_class = "ticker-price-neg" if price < 0 else "ticker-price-pos"
badge_class = "ticker-badge-neg" if price < 0 else "ticker-badge-pos"
if price < 0:
    status = "NEGATIVE PRICE - Charge & Mine Mode"
elif price > MINING_REV_MWH:
    status = "ABOVE MINING BREAKEVEN - Full Grid Dispatch"
else:
    status = "BELOW BREAKEVEN - Mining Profitable"

st.markdown(
    f"""
    <div class="ticker-bar">
        <div>
            <div class="ticker-label">ERCOT West Hub - Real-Time LMP</div>
            <div class="{price_class}">
                {fmt(price, 2)}
                <span style="font-size:20px; font-weight:400; color:#64748b;"> /MWh</span>
            </div>
        </div>
        <div>
            <span class="{badge_class}">{status}</span>
            <div style="font-size:11px; color:#475569; margin-top:8px;">
                Mining Breakeven: <strong style="color:#94a3b8;">${MINING_REV_MWH:.2f}/MWh</strong>
            </div>
        </div>
        <div style="margin-left:auto; text-align:right;">
            <div style="font-size:9px; color:#334155; letter-spacing:1px; text-transform:uppercase;">Data Source</div>
            <div style="font-size:11px; color:#475569; margin-top:2px;">{price_data['source']}</div>
            <div style="font-size:10px; color:#334155; margin-top:4px;">{price_data['timestamp']}</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="section-header">LIVE ASSET STATUS</div>', unsafe_allow_html=True)
g1, g2, g3, g4 = st.columns(4)
miner_active_mw = MINER_MW if price <= MINING_REV_MWH else 0.0
battery_soc = 50.0

with g1:
    st.plotly_chart(make_gauge(solar_mw, SOLAR_CAP_MW, "Solar Output", "MW", "#f59e0b"), use_container_width=True, config={"displayModeBar": False})
with g2:
    st.plotly_chart(make_gauge(wind_mw, WIND_CAP_MW, "Wind Output", "MW", "#3b82f6"), use_container_width=True, config={"displayModeBar": False})
with g3:
    st.plotly_chart(make_gauge(miner_active_mw, MINER_MW, "Miner Load", "MW", "#8b5cf6"), use_container_width=True, config={"displayModeBar": False})
with g4:
    st.plotly_chart(make_gauge(battery_soc, 100, "Battery SOC", "%", "#06b6d4"), use_container_width=True, config={"displayModeBar": False})

p1, p2, p3, p4, p5 = st.columns(5)
pills = [
    (p1, f"Temp: <strong>{weather['temperature_f']}F</strong>"),
    (p2, f"Wind: <strong>{weather['wind_mph']} mph</strong>"),
    (p3, f"GHI: <strong>{weather['solar_w_m2']} W/m2</strong>"),
    (p4, f"Solar CF: <strong>{solar_mw / SOLAR_CAP_MW * 100:.1f}%</strong>"),
    (p5, f"Wind CF: <strong>{wind_mw / WIND_CAP_MW * 100:.1f}%</strong>"),
]
for col, text in pills:
    with col:
        st.markdown(f'<div class="info-pill">{text}</div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<div class="section-header">REVENUE SCENARIOS - CURRENT HOUR</div>', unsafe_allow_html=True)

col_a, col_b, col_c = st.columns(3)

with col_a:
    a_color = "#10b981" if rev_a_hr >= 0 else "#ef4444"
    a_day = rev_a_hr * 24
    st.markdown(
        f"""
        <div class="rev-card">
            <div class="card-title">Scenario A</div>
            <div class="card-subtitle">Renewable Only - Pure Grid Sales</div>
            <div class="card-revenue" style="color:{a_color};">{fmt(rev_a_hr)}</div>
            <div class="card-unit">per hour</div>
            <hr style="border-color:#1e293b; margin:12px 0;">
            <div style="font-size:12px; color:#64748b; line-height:2;">
                <div style="display:flex; justify-content:space-between;">
                    <span>Total Generation</span>
                    <strong style="color:#94a3b8;">{total_gen:.1f} MW</strong>
                </div>
                <div style="display:flex; justify-content:space-between;">
                    <span>ERCOT Price</span>
                    <strong style="color:#94a3b8;">{fmt(price, 2)}/MWh</strong>
                </div>
                <div style="display:flex; justify-content:space-between;">
                    <span>Solar</span>
                    <strong style="color:#f59e0b;">{solar_mw:.1f} MW</strong>
                </div>
                <div style="display:flex; justify-content:space-between;">
                    <span>Wind</span>
                    <strong style="color:#3b82f6;">{wind_mw:.1f} MW</strong>
                </div>
            </div>
            <hr style="border-color:#1e293b; margin:12px 0;">
            <div style="font-size:10px; color:#475569; letter-spacing:1px; text-transform:uppercase;">Projected Daily</div>
            <div style="font-size:22px; font-weight:700; color:#94a3b8; margin-top:4px;">{fmt(a_day)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_b:
    b_day = rev_b_hr * 24
    st.markdown(
        f"""
        <div class="rev-card">
            <div class="card-title">Scenario B</div>
            <div class="card-subtitle">Mining Only - 35 MW, 24/7 Regardless of Price</div>
            <div class="card-revenue">{fmt(rev_b_hr)}</div>
            <div class="card-unit">per hour</div>
            <hr style="border-color:#1e293b; margin:12px 0;">
            <div style="font-size:12px; color:#64748b; line-height:2;">
                <div style="display:flex; justify-content:space-between;">
                    <span>Miner Capacity</span>
                    <strong style="color:#94a3b8;">{MINER_MW:.0f} MW</strong>
                </div>
                <div style="display:flex; justify-content:space-between;">
                    <span>Efficiency</span>
                    <strong style="color:#94a3b8;">{EFFICIENCY_J_TH:.0f} J/TH</strong>
                </div>
                <div style="display:flex; justify-content:space-between;">
                    <span>Hashprice</span>
                    <strong style="color:#94a3b8;">${HASHPRICE}/TH/s/day</strong>
                </div>
                <div style="display:flex; justify-content:space-between;">
                    <span>Mining Rev/MWh</span>
                    <strong style="color:#8b5cf6;">{fmt(MINING_REV_MWH, 2)}</strong>
                </div>
            </div>
            <hr style="border-color:#1e293b; margin:12px 0;">
            <div style="font-size:10px; color:#475569; letter-spacing:1px; text-transform:uppercase;">Projected Daily</div>
            <div style="font-size:22px; font-weight:700; color:#94a3b8; margin-top:4px;">{fmt(b_day)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_c:
    c_day = rev_c_hr * 24
    delta_class = "card-delta-pos" if delta_hr >= 0 else "card-delta-neg"
    delta_icon = "+" if delta_hr >= 0 else "-"
    breakdown_html = "".join(
        f'<div style="display:flex; justify-content:space-between;"><span>{k}</span><strong style="color:#94a3b8;">{fmt(v, 2)}</strong></div>' for k, v in hybrid["breakdown"].items()
    )
    st.markdown(
        f"""
        <div class="rev-card-winner">
            <div class="card-title" style="color:#059669;">Scenario C - OPTIMAL</div>
            <div class="card-subtitle">Hybrid Smart Dispatch Engine</div>
            <div class="card-revenue-green">{fmt(rev_c_hr)}</div>
            <div class="card-unit">per hour</div>
            <div class="{delta_class}">
                {delta_icon} Value Add vs Renewable Only: {fmt(abs(delta_hr))} /hr
            </div>
            <div class="{hybrid['badge_class']}">{hybrid['state']}</div>
            <hr style="border-color:#1a3a2a; margin:14px 0;">
            <div style="font-size:12px; color:#64748b; line-height:2;">
                {breakdown_html}
            </div>
            <hr style="border-color:#1a3a2a; margin:12px 0;">
            <div style="font-size:10px; color:#475569; letter-spacing:1px; text-transform:uppercase;">Projected Daily</div>
            <div style="font-size:22px; font-weight:700; color:#10b981; margin-top:4px;">{fmt(c_day)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<div class="section-header">SCENARIO COMPARISON</div>', unsafe_allow_html=True)

chart_col, kpi_col = st.columns([2, 1])

with chart_col:
    labels = ["A: Renewable Only", "B: Mining Only", "C: Hybrid Optimized"]
    values = [rev_a_hr, rev_b_hr, rev_c_hr]
    colors = ["#3b82f6", "#8b5cf6", "#10b981"]
    bar_fig = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=[fmt(v) for v in values],
            textposition="outside",
            textfont={"color": "#e2e8f0", "size": 14, "family": "Inter"},
            cliponaxis=False,
        )
    )
    bar_fig.add_hline(y=0, line_dash="dot", line_color="#ef4444", line_width=1, annotation_text="$0", annotation_font_color="#ef4444")
    bar_fig.update_layout(
        paper_bgcolor="#0a0e1a",
        plot_bgcolor="#0f172a",
        font={"family": "Inter", "color": "#94a3b8"},
        title={"text": "Hourly Revenue by Strategy", "font": {"size": 14, "color": "#e2e8f0"}},
        yaxis={"title": "Revenue ($/hr)", "gridcolor": "#1e293b", "zeroline": True, "zerolinecolor": "#334155"},
        xaxis={"gridcolor": "#1e293b"},
        showlegend=False,
        margin=dict(l=60, r=30, t=50, b=40),
        height=320,
    )
    st.plotly_chart(bar_fig, use_container_width=True, config={"displayModeBar": False})

with kpi_col:
    best_idx = int(np.argmax([rev_a_hr, rev_b_hr, rev_c_hr]))
    best_labels = ["A: Renewable", "B: Mining", "C: Hybrid"]
    kpis = [
        ("Best Strategy Now", best_labels[best_idx]),
        ("Hybrid Revenue /hr", fmt(rev_c_hr)),
        ("Hybrid Revenue /day", fmt(c_day)),
        ("Value Add /day", fmt(delta_hr * 24)),
        ("Mining Breakeven", f"${MINING_REV_MWH:.2f}/MWh"),
        ("Total Generation", f"{total_gen:.1f} MW"),
        ("Solar CF", f"{solar_mw / SOLAR_CAP_MW * 100:.1f}%"),
        ("Wind CF", f"{wind_mw / WIND_CAP_MW * 100:.1f}%"),
    ]
    st.markdown("**KPI Summary**")
    for label, val in kpis:
        is_delta = "Add" in label
        val_color = "#10b981" if (is_delta and delta_hr >= 0) else "#ef4444" if (is_delta and delta_hr < 0) else "#94a3b8"
        st.markdown(
            f"""
            <div style="display:flex; justify-content:space-between; align-items:center;
                 padding:8px 12px; margin-bottom:4px; background:#0f172a;
                 border:1px solid #1e293b; border-radius:8px;">
                <span style="font-size:11px; color:#64748b;">{label}</span>
                <strong style="font-size:12px; color:{val_color};">{val}</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown('<div class="section-header">24-HOUR WEATHER HISTORY - Midland, TX</div>', unsafe_allow_html=True)
hist_solar_mw = [calc_solar_output(x) for x in hist_df["solar"].tolist()]
hist_wind_mw = [calc_wind_output(x) for x in hist_df["wind_mph"].tolist()]
sp1, sp2 = st.columns(2)

with sp1:
    fig_s = go.Figure(
        go.Scatter(
            x=hist_df["time"],
            y=hist_solar_mw,
            fill="tozeroy",
            fillcolor="rgba(245,158,11,0.12)",
            line={"color": "#f59e0b", "width": 2},
            name="Solar (MW)",
        )
    )
    fig_s.update_layout(
        title={"text": "Solar Output (MW)", "font": {"size": 13, "color": "#e2e8f0"}},
        paper_bgcolor="#0a0e1a",
        plot_bgcolor="#0f172a",
        font={"family": "Inter", "color": "#94a3b8"},
        yaxis={"gridcolor": "#1e293b", "range": [0, SOLAR_CAP_MW + 5]},
        xaxis={"gridcolor": "#1e293b"},
        showlegend=False,
        margin=dict(l=50, r=20, t=40, b=30),
        height=220,
    )
    st.plotly_chart(fig_s, use_container_width=True, config={"displayModeBar": False})

with sp2:
    fig_w = go.Figure(
        go.Scatter(
            x=hist_df["time"],
            y=hist_wind_mw,
            fill="tozeroy",
            fillcolor="rgba(59,130,246,0.12)",
            line={"color": "#3b82f6", "width": 2},
            name="Wind (MW)",
        )
    )
    fig_w.update_layout(
        title={"text": "Wind Output (MW)", "font": {"size": 13, "color": "#e2e8f0"}},
        paper_bgcolor="#0a0e1a",
        plot_bgcolor="#0f172a",
        font={"family": "Inter", "color": "#94a3b8"},
        yaxis={"gridcolor": "#1e293b", "range": [0, WIND_CAP_MW + 5]},
        xaxis={"gridcolor": "#1e293b"},
        showlegend=False,
        margin=dict(l=50, r=20, t=40, b=30),
        height=220,
    )
    st.plotly_chart(fig_w, use_container_width=True, config={"displayModeBar": False})

st.markdown('<div class="section-header">REVENUE SENSITIVITY vs. ERCOT PRICE</div>', unsafe_allow_html=True)
prices_range = np.linspace(-50, 200, 500)
rev_a_range = total_gen * prices_range
rev_b_range = np.full_like(prices_range, MINER_MW * MINING_REV_MWH)
rev_c_range = np.array([smart_dispatch(total_gen, p)["revenue_hr"] for p in prices_range])

sens_fig = go.Figure()
sens_fig.add_trace(
    go.Scatter(
        x=prices_range,
        y=rev_a_range,
        name="A: Renewable Only",
        line={"color": "#3b82f6", "width": 2, "dash": "dot"},
    )
)
sens_fig.add_trace(
    go.Scatter(
        x=prices_range,
        y=rev_b_range,
        name="B: Mining Only",
        line={"color": "#8b5cf6", "width": 2, "dash": "dash"},
    )
)
sens_fig.add_trace(
    go.Scatter(
        x=prices_range,
        y=rev_c_range,
        name="C: Hybrid (Optimal Envelope)",
        line={"color": "#10b981", "width": 3},
    )
)
sens_fig.add_vline(x=price, line_dash="solid", line_color="#fbbf24", line_width=2, annotation_text=f"Now: {fmt(price, 2)}/MWh", annotation_font_color="#fbbf24")
sens_fig.add_vline(
    x=MINING_REV_MWH,
    line_dash="dot",
    line_color="#94a3b8",
    line_width=1,
    annotation_text=f"Breakeven: ${MINING_REV_MWH:.2f}",
    annotation_font_color="#94a3b8",
)
sens_fig.add_vline(x=0, line_dash="dot", line_color="#ef4444", line_width=1)
sens_fig.update_layout(
    paper_bgcolor="#0a0e1a",
    plot_bgcolor="#0f172a",
    font={"family": "Inter", "color": "#94a3b8", "size": 12},
    title={"text": "Hourly Revenue ($/hr) vs. ERCOT West Hub Price ($/MWh)", "font": {"size": 14, "color": "#e2e8f0"}},
    xaxis={"title": "ERCOT Price ($/MWh)", "gridcolor": "#1e293b", "zeroline": True, "zerolinecolor": "#334155"},
    yaxis={"title": "Revenue ($/hr)", "gridcolor": "#1e293b"},
    legend={"bgcolor": "#0f172a", "bordercolor": "#334155", "font": {"color": "#94a3b8"}, "x": 0.01, "y": 0.99},
    margin=dict(l=70, r=30, t=60, b=50),
    height=380,
)
st.plotly_chart(sens_fig, use_container_width=True, config={"displayModeBar": False})

st.markdown('<div class="section-header">SMART DISPATCH DECISION MATRIX</div>', unsafe_allow_html=True)
matrix_df = pd.DataFrame(
    {
        "Price Zone": ["Negative (<$0/MWh)", f"Low ($0 - ${MINING_REV_MWH:.2f}/MWh)", f"High (>${MINING_REV_MWH:.2f}/MWh)"],
        "Strategy": ["Charge Battery + Run Miners", "Run Miners + Sell Remaining to Grid", "Full Grid Dispatch + Discharge Battery"],
        "Miners": ["ON (35 MW)", "ON (35 MW)", "OFF"],
        "Battery": ["Charging (60 MW)", "Standby", "Discharging (60 MW)"],
        "Revenue Driver": ["Neg-Price Arbitrage + Hashrate", "Hashrate Dominates", "Spot Price Premium"],
    }
)
st.dataframe(
    matrix_df.style.set_properties(**{"background-color": "#0f172a", "color": "#e2e8f0", "border-color": "#334155", "font-size": "13px"}).set_table_styles(
        [{"selector": "th", "props": [("background-color", "#1e293b"), ("color", "#94a3b8"), ("font-size", "11px"), ("letter-spacing", "1px")]}]
    ),
    use_container_width=True,
    hide_index=True,
)

st.markdown(
    f"""
    <div style="text-align:center; padding:24px; color:#334155; font-size:11px;
                letter-spacing:1px; margin-top:24px; border-top:1px solid #1e293b;">
        WEST TEXAS RENEWABLE PORTFOLIO DASHBOARD - ERCOT WEST HUB - MIDLAND TX 32.0N 102.1W - 
        DATA AUTO-REFRESHES EVERY 5 MIN - MINING BREAKEVEN: ${MINING_REV_MWH:.2f}/MWh
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### Dashboard Controls")
    if st.button("Force Refresh", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.rerun()
    st.markdown("---")
    st.markdown("**Asset Specifications**")
    specs = [
        ("Solar", f"{SOLAR_CAP_MW:.0f} MW"),
        ("Wind", f"{WIND_CAP_MW:.0f} MW"),
        ("Miners", f"{MINER_MW:.0f} MW"),
        ("Efficiency", f"{EFFICIENCY_J_TH} J/TH"),
        ("Hashprice", f"${HASHPRICE}/TH/s/day"),
        ("Battery", f"{BATTERY_MW:.0f} MW / {BATTERY_MWH:.0f} MWh"),
    ]
    for k, v in specs:
        st.caption(f"**{k}:** {v}")
    st.markdown("---")
    st.markdown("**Live Snapshot**")
    st.metric("ERCOT Price", f"${price:.2f}/MWh", delta="Negative!" if price < 0 else f"+${price:.0f}")
    st.metric("Total Gen", f"{total_gen:.1f} MW", delta=f"Solar {solar_mw:.0f} + Wind {wind_mw:.0f}")
    st.metric("Hybrid Revenue", f"{fmt(rev_c_hr)}/hr", delta=f"{'+' if delta_hr >= 0 else ''}{fmt(delta_hr)} vs Grid-Only")
    st.markdown("---")
    st.caption(f"**State:** {hybrid['state']}")
    st.caption(f"**Mining Rev/MWh:** ${MINING_REV_MWH:.2f}")
    st.caption(f"**Weather Source:** {weather['source']}")
    st.caption(f"**Price Source:** {price_data['source']}")
    if st.button("Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()
```

if **name** == “**main**”:
main()