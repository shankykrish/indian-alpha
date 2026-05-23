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
    
    # Glowing Alert Layout based on regime
    color_map = {
        "BULL_LOW_VOL": "🟢 #00ffcc (Bullish Low Volatility)",
        "BULL_HIGH_VOL": "🔵 #00ccff (Bullish High Volatility - Sizing Safety Recommended)",
        "SIDEWAYS": "🟡 #ffcc00 (Sideways Range Bound - Strict Fills)",
        "RECOVERY": "🟣 #99ff33 (Market Rebounding - Small Exposure Approved)",
        "BEAR": "🟠 #ff6600 (Bear Trend - Cash Conservation)",
        "PANIC": "🔴 #ff3366 (Extreme Systemic Panic - Cash ONLY)"
    }
    
    st.info(f"### ACTIVE REGIME: {color_map.get(regime, regime)}")
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
