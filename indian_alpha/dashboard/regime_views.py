import streamlit as st
import pandas as pd
from typing import List, Dict, Any

def render_regime_panel(regimes_history: List[Dict[str, Any]]):
    """Renders the market regime dashboard, VIX, and breadth telemetry."""
    st.header("🌐 Market Regime Classification Engine")
    
    if not regimes_history:
        st.warning("No regime history recorded yet. Background worker must execute first.")
        return
        
    latest = regimes_history[-1]
    regime = latest.get("regime", "sideways").upper()
    rationale = latest.get("rationale", "")
    telemetry = latest.get("telemetry", {})
    
    # Premium styling configurations per regime
    regime_colors = {
        "BULL_LOW_VOL": {
            "bg": "rgba(0, 255, 204, 0.08)", 
            "border": "#00ffcc", 
            "text": "#00ffcc", 
            "label": "🟢 BULLISH LOW VOLATILITY (High Momentum)"
        },
        "BULL_HIGH_VOL": {
            "bg": "rgba(0, 204, 255, 0.08)", 
            "border": "#00ccff", 
            "text": "#00ccff", 
            "label": "🔵 BULLISH HIGH VOLATILITY (Moderate Sizing)"
        },
        "SIDEWAYS": {
            "bg": "rgba(255, 204, 0, 0.08)", 
            "border": "#ffcc00", 
            "text": "#ffcc00", 
            "label": "🟡 SIDEWAYS RANGE BOUND (Strict Fills / Conservative)"
        },
        "RECOVERY": {
            "bg": "rgba(153, 255, 51, 0.08)", 
            "border": "#99ff33", 
            "text": "#99ff33", 
            "label": "🟣 MARKET REBOUNDING (Accumulation Phase)"
        },
        "BEAR": {
            "bg": "rgba(255, 102, 0, 0.08)", 
            "border": "#ff6600", 
            "text": "#ff6600", 
            "label": "🟠 BEAR TREND (Capital Preservation)"
        },
        "PANIC": {
            "bg": "rgba(255, 51, 102, 0.08)", 
            "border": "#ff3366", 
            "text": "#ff3366", 
            "label": "🔴 SYSTEMIC PANIC (Cash Preservation ONLY)"
        }
    }
    
    cfg = regime_colors.get(regime, {
        "bg": "rgba(255, 255, 255, 0.05)", 
        "border": "rgba(255, 255, 255, 0.1)", 
        "text": "#ffffff", 
        "label": regime
    })
    
    # Premium Glowing Active Regime Card
    st.markdown(f"""
    <div style="
        background: {cfg['bg']}; 
        border: 1px solid {cfg['border']}; 
        border-radius: 12px; 
        padding: 24px; 
        text-align: center; 
        margin-bottom: 25px; 
        box-shadow: 0 4px 20px {cfg['bg']};
    ">
        <h4 style="
            color: #a0a0b0; 
            margin: 0 0 8px 0; 
            font-family: 'Inter', sans-serif; 
            font-size: 14px; 
            text-transform: uppercase; 
            letter-spacing: 1.5px;
            font-weight: 600;
        ">Active Market Regime</h4>
        <h2 style="
            color: {cfg['text']}; 
            margin: 0; 
            font-family: 'Outfit', sans-serif; 
            font-size: 24px; 
            font-weight: 800;
            background: none;
            -webkit-text-fill-color: initial;
        ">{cfg['label']}</h2>
    </div>
    """, unsafe_allow_html=True)
    st.write(f"**Classification Rationale:** {rationale}")
    
    st.write("---")
    
    # Telemetry Columns
    st.subheader("📊 Systemic Market Telemetry")
    col1, col2, col3 = st.columns(3)
    
    breadth = telemetry.get("breadth", {})
    with col1:
        st.metric("India VIX Level", f"{telemetry.get('india_vix', 15.0):.2f}", "Stable" if telemetry.get('india_vix', 15.0) < 18 else "Volatile")
    with col2:
        st.metric("Market Breadth (% > 50 DMA)", f"{breadth.get('pct_above_50dma', 50.0):.1f}%")
    with col3:
        st.metric("Advance/Decline Ratio", f"{breadth.get('advance_decline_ratio', 1.0):.2f}")
        
    st.write("---")
    
    # Sector Rotations
    st.subheader("🎯 Sector Rotation Leadership")
    sector_scores = telemetry.get("sector_scores", {})
    if sector_scores:
        s_df = pd.DataFrame(list(sector_scores.items()), columns=["Sector Index", "20-Day Momentum Return %"])
        s_df = s_df.sort_values(by="20-Day Momentum Return %", ascending=False)
        st.dataframe(s_df, use_container_width=True, hide_index=True)
    else:
        st.info("No sectoral rotation momentum logged.")
