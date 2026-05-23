import streamlit as st
import pandas as pd
from typing import Dict, Any

def render_rankings_panel(rankings_data: Dict[str, Any]):
    """Renders the composite momentum ranking table with interactive filters."""
    st.header("🎯 Live Momentum Composite Stock Rankings")
    
    if not rankings_data or not rankings_data.get("rankings"):
        st.warning("No rankings records found. Background worker must execute scans.")
        return
        
    last_updated = rankings_data.get("last_updated", "Unknown")
    st.write(f"*Rankings computed at: {last_updated} (Asia/Kolkata)*")
    
    rankings_list = rankings_data.get("rankings", [])
    df = pd.DataFrame(rankings_list)
    
    # 1. Interactive Filters Row
    col1, col2 = st.columns(2)
    with col1:
        selected_theme = st.selectbox("Filter by Theme/Focus Area", ["All Themes", "PSU", "Defense", "Railway", "Capital Goods", "General"])
    with col2:
        min_score = st.slider("Minimum Composite Score (0-100)", 0.0, 100.0, 50.0)
        
    # Apply Filters
    filtered_df = df.copy()
    if selected_theme != "All Themes":
        filtered_df = filtered_df[filtered_df["theme"] == selected_theme]
    filtered_df = filtered_df[filtered_df["composite_score"] >= min_score]
    
    # Format table for high aesthetic value
    if filtered_df.empty:
        st.info("No stock candidates match current filter thresholds.")
    else:
        display_rows = []
        for _, r in filtered_df.iterrows():
            factors = r.get("factors", {})
            display_rows.append({
                "Rank": len(display_rows) + 1,
                "Symbol": r["symbol"],
                "Company Name": r["name"],
                "Theme": r["theme"],
                "Close (₹)": f"{r['close']:,.2f}",
                "1D % Change": f"{r['pct_change_1d']:+.2f}%",
                "Composite Momentum Score": f"{r['composite_score']:.2f}",
                "RS vs NIFTY (60d)": f"{factors.get('rs_vs_nifty', 0.0):+.2f}%",
                "Deliv Exp (5d/20d)": f"{factors.get('delivery_expansion', 1.0):.2f}x",
                "Dist from 20d High": f"{factors.get('breakout_proximity_pct', 0.0):.2f}%"
            })
            
        st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)
