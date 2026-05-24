import streamlit as st
import pandas as pd
from typing import Dict, Any
from datetime import datetime
from indian_alpha.storage.universes import MIDCAP_100, SMALLCAP_100

def render_rankings_panel(rankings_data: Dict[str, Any]):
    """Renders the composite momentum ranking tables with interactive filters."""
    st.header("🎯 Live Momentum Composite Stock Rankings")
    
    if not rankings_data or not rankings_data.get("rankings"):
        st.warning("No rankings records found. Background worker must execute scans.")
        return
        
    last_updated = rankings_data.get("last_updated", "Unknown")
    try:
        dt = datetime.fromisoformat(last_updated)
        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        formatted_time = last_updated
        
    st.write(f"*Rankings computed at: {formatted_time} (Asia/Kolkata)*")
    
    rankings_list = rankings_data.get("rankings", [])
    df = pd.DataFrame(rankings_list)
    
    # Ensure backward compatibility for universe_type
    if "universe_type" not in df.columns:
        df["universe_type"] = df.apply(lambda r: "Midcap" if r["symbol"] in MIDCAP_100 else "Smallcap", axis=1)
    
    # 1. Interactive Filters Row
    col1, col2 = st.columns(2)
    with col1:
        selected_theme = st.selectbox("Filter by Theme/Focus Area", ["All Themes", "PSU", "Defense", "Railway", "Capital Goods", "General"])
    with col2:
        min_score = st.slider("Minimum Composite Score (0-100)", 0.0, 100.0, 40.0)
        
    # Apply Filters
    filtered_df = df.copy()
    if selected_theme != "All Themes":
        filtered_df = filtered_df[filtered_df["theme"] == selected_theme]
    filtered_df = filtered_df[filtered_df["composite_score"] >= min_score]
    
    # Split into Midcap and Smallcap
    midcap_df = filtered_df[filtered_df["universe_type"] == "Midcap"].copy()
    smallcap_df = filtered_df[filtered_df["universe_type"] == "Smallcap"].copy()
    
    # Helper to draw beautiful tables
    def draw_leader_table(leader_df, title, icon):
        st.markdown(f"### {icon} {title}")
        if leader_df.empty:
            st.info("No stock candidates match current filter thresholds.")
            return
            
        display_rows = []
        for idx, (_, r) in enumerate(leader_df.iterrows()):
            factors = r.get("factors", {})
            display_rows.append({
                "Rank": idx + 1,
                "Symbol": r["symbol"],
                "Company Name": r["name"],
                "Theme": r["theme"],
                "Close (₹)": f"{r['close']:,.2f}",
                "1D % Change": f"{r['pct_change_1d']:+.2f}%",
                "Momentum Score": f"{r['composite_score']:.2f}",
                "RS vs NIFTY (60d)": f"{factors.get('rs_vs_nifty', 0.0):+.2f}%",
                "Deliv Exp (5d/20d)": f"{factors.get('delivery_expansion', 1.0):.2f}x",
                "Dist from 20d High": f"{factors.get('breakout_proximity_pct', 0.0):.2f}%"
            })
            
        st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)

    # 2. Render stacked tables
    st.write("---")
    draw_leader_table(midcap_df, "Top 15 Midcap Momentum Leaders", "🏆")
    
    st.write("---")
    draw_leader_table(smallcap_df, "Top 15 Smallcap Momentum Leaders", "🚀")

