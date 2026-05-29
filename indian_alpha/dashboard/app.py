import streamlit as st
import os
import json
from loguru import logger

# Set page config at the very top
st.set_page_config(
    page_title="Indian-Alpha Platform",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium dark styling overrides
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=Outfit:wght@400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .stApp {
        background-color: #0d0d11;
        color: #e0e0ea;
    }
    
    h1, h2, h3 {
        font-family: 'Outfit', sans-serif;
        font-weight: 800;
        background: linear-gradient(135deg, #00ffcc 0%, #00ccff 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .stMetric {
        background-color: #15151e !important;
        border: 1px solid rgba(255,255,255,0.05);
        border-radius: 12px;
        padding: 15px !important;
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
    }
    
    div[data-testid="metric-container"] label {
        color: #a0a0b0 !important;
        font-weight: 600 !important;
    }
    
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
        color: #ffffff !important;
        font-weight: 800 !important;
    }
    
    /* Sleek buttons */
    .stButton>button {
        background: linear-gradient(135deg, #00ffcc 0%, #00ccff 100%);
        color: #0b0b0f !important;
        font-weight: bold !important;
        border: none !important;
        border-radius: 8px !important;
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(0, 255, 204, 0.4);
    }
</style>
""", unsafe_allow_html=True)

# Import View Panels
from indian_alpha.dashboard.portfolio_views import render_portfolio_panel
from indian_alpha.dashboard.regime_views import render_regime_panel
from indian_alpha.dashboard.rankings_views import render_rankings_panel
from indian_alpha.dashboard.reflection_views import render_reflection_panel
from indian_alpha.dashboard.strategy_views import render_strategy_panel
from indian_alpha.dashboard.health_views import render_health_panel
from indian_alpha.dashboard.trade_views import render_trade_journal_panel

# Import Core Storage Engines
from indian_alpha.storage.trades import load_trades
from indian_alpha.storage.rankings import load_rankings
from indian_alpha.storage.hypotheses import load_hypotheses
from indian_alpha.storage.strategy_store import load_strategy
from indian_alpha.storage.market_regimes import load_regimes_history
from indian_alpha.storage.snapshots import load_latest_portfolio_snapshot

def main():
    st.sidebar.markdown("# 🎯 Indian-Alpha")
    st.sidebar.markdown("### Self-Learning Quantitative Platform")
    st.sidebar.write("---")
    
    # Navigation Sidebar
    nav = st.sidebar.radio(
        "Navigation",
        [
            "💼 Portfolio & Performance",
            "🎯 Live Rankings",
            "🌐 Market Regimes",
            "🧠 Cognitive Reflection",
            "⚙️ Active Strategy Settings",
            "📖 Trade Journal",
            "🩺 System Health Telemetry"
        ]
    )
    
    st.sidebar.write("---")
    
    # Auto-refresh helper button
    if st.sidebar.button("🔄 Sync State"):
        st.rerun()
        
    # Render Zerodha connection status & OAuth panel
    from indian_alpha.dashboard.zerodha_views import render_zerodha_auth_sidebar
    render_zerodha_auth_sidebar()
        
    st.sidebar.markdown("""
    **Timezone:** `Asia/Kolkata`
    **Persistent Storage:** `/app/state`
    **Execution Mode:** `Railway Deployable`
    """)

    # Load shared state database from persistence layers
    trades = load_trades()
    rankings = load_rankings()
    hypotheses = load_hypotheses()
    strategy = load_strategy()
    regimes = load_regimes_history()
    portfolio = load_latest_portfolio_snapshot()
    
    # Fallback default portfolio values if no snapshot has been written by run.py yet
    if not portfolio:
        portfolio = {
            "cash": 1000000.0,
            "positions": {},
            "total_equity": 1000000.0
        }

    # Routing Panels
    if nav == "💼 Portfolio & Performance":
        render_portfolio_panel(portfolio)
        
        # Draw Performance Charts in this main panel
        if trades:
            st.write("---")
            st.subheader("📈 Performance History & Analytics")
            from indian_alpha.dashboard.charts import draw_equity_curve, draw_drawdown_curve
            
            # Reconstruct history entries from trades to draw simple equity curve
            # If no history written yet, we compile a mock one based on trades PnLs
            closed_trades = [t for t in trades if t.get("action") == "SELL"]
            history = [{"timestamp": datetime.now() - timedelta(days=len(closed_trades)-i), "total_equity": 1000000.0 + sum([(x.get("pnl") if x.get("pnl") is not None else 0.0) for x in closed_trades[:i+1]])} for i, t in enumerate(closed_trades)]
            
            # Include start baseline
            history.insert(0, {"timestamp": datetime.now() - timedelta(days=len(closed_trades)+1), "total_equity": 1000000.0})
            
            c_col1, c_col2 = st.columns(2)
            with c_col1:
                st.plotly_chart(draw_equity_curve(history), use_container_width=True)
            with c_col2:
                st.plotly_chart(draw_drawdown_curve(history), use_container_width=True)
                
    elif nav == "🎯 Live Rankings":
        render_rankings_panel(rankings)
        
    elif nav == "🌐 Market Regimes":
        render_regime_panel(regimes)
        
        # Include Donut chart
        if regimes:
            st.write("---")
            from indian_alpha.dashboard.charts import draw_regime_donut
            st.plotly_chart(draw_regime_donut(regimes), use_container_width=True)
            
    elif nav == "🧠 Cognitive Reflection":
        render_reflection_panel(hypotheses)
        
    elif nav == "⚙️ Active Strategy Settings":
        render_strategy_panel(strategy)
        
    elif nav == "📖 Trade Journal":
        render_trade_journal_panel(trades)
        
    elif nav == "🩺 System Health Telemetry":
        render_health_panel()

if __name__ == "__main__":
    from datetime import datetime, timedelta
    main()
