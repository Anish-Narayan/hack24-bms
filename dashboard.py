import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from analytics import BMSAnalytics
import time
import os

# --- CONFIG ---
st.set_page_config(page_title="Industrial BMS Pro", layout="wide", page_icon="🔋")

# Custom CSS for a professional look
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    /* Success/Positive Metric Color */
    [data-testid="stMetricValue"] {
        color: #00ff00;
    }
    </style>
    """, unsafe_allow_html=True) # FIXED TYPO HERE

@st.cache_data(ttl=5)
def load_data():
    file = "battery_master_log.csv"
    if not os.path.exists(file) or os.stat(file).st_size == 0:
        return pd.DataFrame()
    
    df = pd.read_csv(file)
    if df.empty:
        return df
        
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    # Signal Smoothing: Clean up sensor noise
    df['v_smooth'] = df['voltage_v'].rolling(window=3, min_periods=1).mean()
    df['p_smooth'] = df['power_w'].rolling(window=3, min_periods=1).mean()
    return df

# --- HEADER & SIDEBAR ---
st.title("🛡️ Advanced Energy Management System")
st.sidebar.header("System Settings")
auto_refresh = st.sidebar.toggle("Real-time Auto-Refresh", value=True)
refresh_rate = st.sidebar.slider("Sampling Rate (s)", 2, 60, 5)

try:
    df = load_data()
    
    if df.empty or len(df) < 2:
        st.warning("📥 Waiting for more telemetry data... Ensure logger.py is running.")
        if auto_refresh:
            time.sleep(2)
            st.rerun()
        st.stop()

    engine = BMSAnalytics()
    metrics = engine.analyze()
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    # --- TOP ROW: KPI CARDS ---
    c1, c2, c3, c4, c5 = st.columns(5)
    
    # Calculate deltas safely
    pct_delta = int(latest['pct'] - prev['pct'])
    v_delta = float(latest['voltage_v'] - prev['voltage_v'])

    c1.metric("Current Charge", f"{latest['pct']}%", f"{pct_delta}%")
    c2.metric("Health Score", f"{metrics['Health Score']}/100")
    c3.metric("Voltage", f"{latest['voltage_v']:.2f} V", f"{v_delta:.3f} V")
    c4.metric("Thermal Load", f"{latest['temp_c']}°C")
    c5.metric("Cycle Wear", int(latest['cycles']))

    # --- MAIN ANALYTICS TABS ---
    tab1, tab2, tab3 = st.tabs(["⚡ Live Telemetry", "📈 Historical Trends", "🩺 Deep Diagnostics"])

    with tab1:
        # Dual-Axis Plotly Chart
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        # Power Trace
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['p_smooth'], 
                                 name="Power Draw (W)", fill='tozeroy',
                                 line=dict(color='#ff4b4b', width=2)), secondary_y=False)
        
        # Voltage Trace
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['v_smooth'], 
                                 name="Voltage (V)",
                                 line=dict(color='#00d4ff', width=3)), secondary_y=True)

        fig.update_layout(title="Load vs. Voltage Stability", 
                          hovermode="x unified",
                          template="plotly_dark", 
                          height=500,
                          legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        
        fig.update_yaxes(title_text="<b>Power</b> (Watts)", secondary_y=False)
        fig.update_yaxes(title_text="<b>Voltage</b> (Volts)", secondary_y=True)
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Capacity History")
            fig_cap = go.Figure(go.Scatter(x=df['timestamp'], y=df['pct'], fill='tozeroy', line=dict(color='green')))
            fig_cap.update_layout(template="plotly_dark", height=300)
            st.plotly_chart(fig_cap, use_container_width=True)
        with col_b:
            st.subheader("Thermal Profile")
            fig_temp = go.Figure(go.Histogram(x=df['temp_c'], marker_color='#ffa500'))
            fig_temp.update_layout(template="plotly_dark", height=300)
            st.plotly_chart(fig_temp, use_container_width=True)

    with tab3:
        st.subheader("System Diagnostics")
        d1, d2 = st.columns(2)
        with d1:
            st.info(f"**State of Health (SoH):** {metrics['SoH (%)']}%")
            st.info(f"**Stability Index:** {metrics['Stability Index']}%")
            st.info(f"**Discharge Velocity:** {metrics['Discharge Rate']}% / sample")
        with d2:
            st.write("**Active Alerts & Optimization**")
            if not metrics["Recommendations"]:
                st.success("✅ Battery operating within nominal parameters.")
            for r in metrics["Recommendations"]:
                st.warning(r)

    # --- RAW DATA ---
    with st.expander("Explore Raw Telemetry (Last 100 Frames)"):
        st.dataframe(df.tail(100).sort_values(by='timestamp', ascending=False), use_container_width=True)

except Exception as e:
    st.error(f"Waiting for Data... {e}")

# Auto-refresh logic
if auto_refresh:
    time.sleep(refresh_rate)
    st.rerun()