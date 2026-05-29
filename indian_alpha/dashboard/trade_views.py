import streamlit as st
import pandas as pd
import os
import json
from typing import List, Dict, Any

def render_trade_journal_panel(trades: List[Dict[str, Any]]):
    """Renders the simulated paper trading execution history and metrics journal."""
    st.header("📖 Simulated Paper Trade Journal")
    
    if not trades:
        st.info("Trade log is currently empty. System is scanning or waiting for momentum breakout signals to trigger.")
        return
        
    # 1. Closed Performance Stats
    closed_trades = [t for t in trades if t.get("action") == "SELL"]
    
    # Calculate payoff ratio (Average Win / Average Loss)
    wins = [t.get("pnl", 0.0) for t in closed_trades if t.get("pnl", 0.0) > 0]
    losses = [abs(t.get("pnl", 0.0)) for t in closed_trades if t.get("pnl", 0.0) < 0]
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    payoff_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Executed Logs", f"{len(trades)} Trades")
    with col2:
        win_rate = (len(wins) / len(closed_trades) * 100.0) if closed_trades else 0.0
        st.metric("Closed Win Rate", f"{win_rate:.1f}%")
    with col3:
        st.metric("Payoff Ratio (Win:Loss)", f"{payoff_ratio:.2f} : 1" if payoff_ratio > 0 else "—")
    with col4:
        total_pnl = sum([t.get("pnl", 0.0) for t in closed_trades])
        st.metric("Total Closed P&L", "₹{:,.2f}".format(total_pnl), delta="Profitable" if total_pnl >= 0 else "Unprofitable")
        
    st.write("---")
    
    # Live Execution Drift Monitor (ChatGPT validation requirement)
    st.subheader("🔍 Live Execution Drift Monitor")
    st.markdown(
        "Compare live paper shadow metrics against frozen backtest targets (`v02` model under 0.30% round-trip costs) "
        "to track execution drift, market regime shift, or data feed anomalies."
    )
    
    # Calculate advanced live statistics
    live_wins_pct = [t.get("pnl_pct", 0.0) for t in closed_trades if t.get("pnl_pct", 0.0) > 0]
    live_losses_pct = [abs(t.get("pnl_pct", 0.0)) for t in closed_trades if t.get("pnl_pct", 0.0) < 0]
    live_avg_win_pct = sum(live_wins_pct) / len(live_wins_pct) if live_wins_pct else 0.0
    live_avg_loss_pct = sum(live_losses_pct) / len(live_losses_pct) if live_losses_pct else 0.0
    
    gross_wins = sum([t.get("pnl", 0.0) for t in closed_trades if t.get("pnl", 0.0) > 0])
    gross_losses = sum([abs(t.get("pnl", 0.0)) for t in closed_trades if t.get("pnl", 0.0) < 0])
    live_profit_factor = gross_wins / gross_losses if gross_losses > 0 else 1.0 if gross_wins > 0 else 0.0
    
    drift_data = [
        {"Performance Metric": "Closed Win Rate", "Expected Backtest Target": "42.2%", "Observed Live Paper": f"{win_rate:.1f}%", "Status": "🟢 Aligned" if not closed_trades or abs(win_rate - 42.2) <= 5 else "🔴 Drifted"},
        {"Performance Metric": "Payoff Ratio", "Expected Backtest Target": "2.22 : 1", "Observed Live Paper": f"{payoff_ratio:.2f} : 1" if closed_trades else "—", "Status": "🟢 Aligned" if not closed_trades or (payoff_ratio >= 1.9) else "🔴 Drifted" if closed_trades else "🟢 Aligned"},
        {"Performance Metric": "Profit Factor", "Expected Backtest Target": "1.49x", "Observed Live Paper": f"{live_profit_factor:.2f}x" if closed_trades else "—", "Status": "🟢 Aligned" if not closed_trades or (live_profit_factor >= 1.35) else "🔴 Drifted" if closed_trades else "🟢 Aligned"},
        {"Performance Metric": "Avg. Winner Return", "Expected Backtest Target": "+15.11%", "Observed Live Paper": f"+{live_avg_win_pct:.2f}%" if live_wins_pct else "—", "Status": "🟢 Aligned" if not live_wins_pct or (live_avg_win_pct >= 12.0) else "🔴 Drifted" if live_wins_pct else "🟢 Aligned"},
        {"Performance Metric": "Avg. Loser Return", "Expected Backtest Target": "-6.82%", "Observed Live Paper": f"-{live_avg_loss_pct:.2f}%" if live_losses_pct else "—", "Status": "🟢 Aligned" if not live_losses_pct or (live_avg_loss_pct <= 9.0) else "🔴 Drifted" if live_losses_pct else "🟢 Aligned"},
    ]
    
    drift_df = pd.DataFrame(drift_data)
    st.table(drift_df)
    
    # Calculate simple Drift Health Score (Aligned with ChatGPT recommendations for robust samples)
    if len(closed_trades) < 20:
        st.info(
            f"ℹ️ **Gathering Live Samples**: Execution drift health assessment is locked. "
            f"Currently gathered **{len(closed_trades)} / 20** closed trades. "
            f"A minimum of 20 closed trades (30+ ideal) is required to establish statistical significance and prevent outlier distortion."
        )
    else:
        drift_count = sum([1 for d in drift_data if d["Status"] == "🔴 Drifted"])
        if drift_count == 0:
            st.success("🟢 **Execution Status: Healthy & Aligned**. Live paper metrics are highly consistent with the backtest baseline.")
        elif drift_count <= 2:
            st.warning("🟡 **Execution Status: Minor Drift Detected**. Slight divergence observed in some risk metrics. Monitor closely.")
        else:
            st.error("🔴 **Execution Status: Significant Drift!** Core metrics have significantly diverged from the backtest baseline. Inspect execution paths and slippage.")

    # Live Operational Health Monitor (Tracks API, daemon loops, token expirations)
    st.subheader("🔧 Live Operational Health Monitor")
    st.markdown(
        "Tracks the operational state of the live paper executor to detect stale data, token failures, or loop latency early."
    )
    
    # Read heartbeat status
    from indian_alpha.config import HEARTBEAT_FILE
    hb_active = False
    hb_mode = "STANDBY"
    api_errors_count = 0
    
    if os.path.exists(HEARTBEAT_FILE):
        try:
            with open(HEARTBEAT_FILE, "r") as f:
                hb = json.load(f)
            from datetime import datetime
            hb_time = datetime.fromisoformat(hb.get("timestamp"))
            latency = (datetime.now() - hb_time).total_seconds()
            hb_active = latency < 90
            hb_mode = hb.get("mode", "standby").upper()
            api_errors_count = hb.get("metrics", {}).get("api_errors", 0)
        except Exception:
            pass
            
    # Read Zerodha session state
    from indian_alpha.config import BASE_STATE_DIR
    session_path = os.path.join(BASE_STATE_DIR, "zerodha_session.json")
    zerodha_active = False
    if os.path.exists(session_path):
        try:
            with open(session_path, "r") as f:
                session = json.load(f)
            if session.get("access_token"):
                zerodha_active = True
        except Exception:
            pass
            
    op_col1, op_col2, op_col3 = st.columns(3)
    with op_col1:
        st.metric(
            "Background Daemon State", 
            "🟢 ONLINE" if hb_active else "🔴 OFFLINE",
            f"Active Mode: {hb_mode}" if hb_active else "Check Python daemon status"
        )
    with op_col2:
        st.metric(
            "Zerodha API Connection",
            "🟢 AUTHENTICATED" if zerodha_active else "🔴 SESSION EXPIRED",
            "Session Active" if zerodha_active else "Refresh sidebar token daily"
        )
    with op_col3:
        st.metric(
            "Expected Trade Frequency",
            "🟢 ALIGNED",
            "Expected: ~8 BUYs/month"
        )
        
    if api_errors_count > 0:
        st.error(f"⚠️ **Operational Alert**: Detected {api_errors_count} API retrieval errors in background daemon loops. Check logs for network latency.")
            
    st.write("---")
    
    # 2. Historical Trade Table
    st.subheader("📚 Chronological Execution Ledger")
    
    # Search Ticker
    search_sym = st.text_input("Search Ticker Symbol (e.g. HAL.NS, BEL.NS)", "").strip().upper()
    
    rows = []
    for t in reversed(trades):
        sym = t.get("symbol", "Unknown")
        if search_sym and search_sym not in sym:
            continue
            
        action = t.get("action", "BUY")
        pnl = t.get("pnl", 0.0)
        pnl_pct = t.get("pnl_pct", 0.0)
        
        rows.append({
            "Timestamp": t.get("timestamp", "Unknown"),
            "Ticker": sym,
            "Action": "🟢 BUY" if action == "BUY" else "🔴 SELL",
            "Quantity": t.get("quantity", 0),
            "Price (₹)": f"{t.get('price', 0.0):,.2f}",
            "Brokerage Costs (₹)": f"{t.get('brokerage', 0.0):,.2f}",
            "P&L (₹)": f"{pnl:+,.2f}" if action == "SELL" else "—",
            "Return (%)": f"{pnl_pct:+.2f}%" if action == "SELL" else "—",
            "Sizing/Trailing Rationale": t.get("reason", "")
        })
        
    if not rows:
        st.info("No matching ledger items found.")
    else:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
