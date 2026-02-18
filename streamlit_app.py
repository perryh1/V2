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

# --- 2. BALANCED AUTHENTICATION PORTAL ---
if "password_correct" not in st.session_state: 
    st.session_state.password_correct = False

def check_password():
    if st.session_state.password_correct: return True
    
    st.markdown("""
        <style>
        .stApp { background-color: #0e1117; }
        
        .flex-container {
            display: flex;
            flex-wrap: wrap;
            min-height: 100vh;
            width: 100%;
        }
        
        .login-sidebar {
            background-color: #262730;
            flex: 1 1 350px;
            padding: 60px 40px;
            color: white;
            border-right: 1px solid #3d3f4b;
            display: flex;
            flex-direction: column;
        }
        
        .login-main {
            flex: 3 1 500px;
            display: flex;
            align-items: center; /* Vertically Centers Card */
            justify-content: center; /* Horizontally Centers Card */
            padding: 40px;
            background-color: #0e1117;
        }
        
        .brand-text { color: #ffffff; font-family: 'Inter', sans-serif; font-weight: 800; font-size: 38px; margin-bottom: 5px; }
        .version-text { color: #808495; font-size: 14px; margin-bottom: 40px; }
        
        .auth-card {
            background: #161b22;
            padding: 50px;
            border-radius: 12px;
            border: 1px solid #30363d;
            width: 100%;
            max-width: 600px; /* Wider for desktop legibility */
            box-shadow: 0 20px 50px rgba(0,0,0,0.3);
        }
        
        .auth-header { color: #ffffff; font-weight: 700; font-size: 28px; margin-bottom: 8px; }
        .auth-sub { color: #8b949e; font-size: 15px; margin-bottom: 30px; }
        
        .brief-section { color: #c9d1d9; font-size: 14px; line-height: 1.7; margin-bottom: 35px; border-left: 3px solid #0052FF; padding-left: 20px; }
        .brief-title { color: #58a6ff; font-weight: 600; font-size: 13px; text-transform: uppercase; margin-bottom: 12px; letter-spacing: 1.2px; }

        @media (max-width: 992px) {
            .login-sidebar { min-height: auto; border-right: none; border-bottom: 1px solid #3d3f4b; flex: 1 1 100%; }
            .login-main { padding: 40px 20px; flex: 1 1 100%; align-items: flex-start; }
            .auth-card { padding: 30px; }
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="flex-container">', unsafe_allow_html=True)
    
    # Left Section: Branding
    st.markdown(f'''
        <div class="login-sidebar">
            <p class="brand-text">Hybrid OS</p>
            <p class="version-text">v13.3 Deployment</p>
        </div>
    ''', unsafe_allow_html=True)
    
    # Right Section: Content
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
st.sidebar.caption("v13.3 Deployment")
st.sidebar.write("---")

# [Rest of your dashboard code here...]
