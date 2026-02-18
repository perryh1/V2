# --- UPDATED APP CONFIG ---
st.set_page_config(layout="wide", page_title="Grid Alpha | Hybrid Intelligence")

# --- UPDATED AUTHENTICATION PORTAL ---
def check_password():
    if st.session_state.password_correct: return True
    
    # Professional CSS remains, only text changed for branding
    st.markdown("""
        <style>
        .login-container { max-width: 450px; margin: auto; padding: 40px; background: white; border-radius: 12px; }
        .main-title { color: #1a1a1a; font-family: 'Inter', sans-serif; font-weight: 700; font-size: 26px; }
        .sub-title { color: #6c757d; font-family: 'Inter', sans-serif; font-size: 14px; }
        </style>
    """, unsafe_allow_html=True)

    _, col_mid, _ = st.columns([1, 1, 1])
    with col_mid:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        st.markdown('<p class="main-title">Grid Alpha</p>', unsafe_allow_html=True)
        st.markdown('<p class="sub-title">Hybrid Asset Optimization & Yield Analytics</p>', unsafe_allow_html=True)
        
        pwd = st.text_input("Access Key", type="password")
        
        if st.button("Authenticate Session", use_container_width=True, type="primary"):
            if pwd == DASHBOARD_PASSWORD:
                st.session_state.password_correct = True
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    return False
