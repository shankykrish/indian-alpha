import streamlit as st
import pandas as pd
from typing import List, Dict, Any

def render_trade_journal_panel(trades: List[Dict[str, Any]]):
    """Renders the simulated paper trading execution history and metrics journal."""
    st.header("📖 Simulated Paper Trade Journal")
    
    if not trades:
        st.info("Trade log is currently empty. System is scanning or waiting for momentum breakout signals to trigger.")
        return
        
    # 1. Closed Performance Stats
    closed_trades = [t for t in trades if t.get("action") == "SELL"]
    open_trades_count = len([t for t in trades if t.get("action") == "BUY"]) - len(closed_trades)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Executed Logs", f"{len(trades)} Trades")
    with col2:
        st.metric("Closed Positions", f"{len(closed_trades)} Trades")
    with col3:
        win_rate = (len([t for t in closed_trades if t.get("pnl", 0.0) > 0]) / len(closed_trades) * 100.0) if closed_trades else 0.0
        st.metric("Closed Win Rate", f"{win_rate:.1f}%")
    with col4:
        total_pnl = sum([t.get("pnl", 0.0) for t in closed_trades])
        st.metric("Total Closed P&L", "₹{:,.2f}".format(total_pnl), delta="Profitable" if total_pnl >= 0 else "Unprofitable")
        
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
