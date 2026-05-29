import streamlit as st
import pandas as pd
import json
import os
import asyncio
import plotly.graph_objects as go
from typing import Dict, Any

from indian_alpha.config import BASE_STATE_DIR
from indian_alpha.storage.strategy_store import load_strategy

def render_backtest_panel():
    """Renders the historical backtesting research panel inside the Streamlit dashboard."""
    st.header("🔬 Quant Historical Backtesting Research")
    st.caption("Evaluate your strategy rules over a multi-year time horizon using high-fidelity historical data, dynamic ATR stop channels, and gap slippage execution model.")
    st.write("---")

    results_file = os.path.join(BASE_STATE_DIR, "backtest_results.json")
    
    # Check if we need to trigger backtest dynamically from UI
    trigger_run = False
    
    if not os.path.exists(results_file):
        st.warning("⚠️ No historical backtest data found. Run a simulation to compile performance analytics.")
        if st.button("⚡ Run Full 5-Year Backtest (2021 - 2026)", use_container_width=True):
            trigger_run = True
    else:
        # Load active results
        try:
            with open(results_file, "r") as f:
                results = json.load(f)
        except Exception as e:
            st.error(f"Failed to read backtest results: {e}")
            results = None
            
        if results:
            sum_data = results.get("summary", {})
            
            # --- 1. RENDER KEY PERFORMANCE METRICS ---
            st.subheader("📊 Backtest Strategy Key Telemetry")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Compound Growth (CAGR)", f"{sum_data.get('cagr', 0.0):.2f}%", help="Annualized compounded return rate")
            with col2:
                st.metric("Maximum Drawdown", f"-{sum_data.get('max_drawdown', 0.0):.2f}%", help="Peak-to-trough maximum account decline")
            with col3:
                st.metric("Payoff Ratio (Win:Loss)", f"{sum_data.get('payoff_ratio', 0.0):.2f} : 1", help="Average Win % vs Average Loss %")
            with col4:
                st.metric("Profit Factor", f"{sum_data.get('profit_factor', 1.0):.2f}x", help="Gross profits divided by gross losses")
                
            col1_b, col2_b, col3_b, col4_b = st.columns(4)
            with col1_b:
                st.metric("Account Value (Final)", "₹{:,.2f}".format(sum_data.get("final_equity", 1000000.0)))
            with col2_b:
                st.metric("Closed Win Rate", f"{sum_data.get('win_rate', 0.0):.1f}%")
            with col3_b:
                st.metric("Executed Logs", f"{sum_data.get('total_trades', 0)} Trades")
            with col4_b:
                st.metric("Simulation Window", "5.4 Years")
                
            st.write("---")
            
            # --- 2. RENDER PLOTLY COMPARATIVE EQUITY CHART ---
            st.subheader("📈 Growth Curve Comparison (Portfolio vs. Nifty-50 Benchmark)")
            equity_curve = results.get("equity_curve", [])
            if equity_curve:
                df_eq = pd.DataFrame(equity_curve)
                df_eq["date"] = pd.to_datetime(df_eq["date"])
                
                # Normalize both to 100 at start to show comparative growth
                first_port = df_eq["portfolio_equity"].iloc[0]
                first_nifty = df_eq["nifty_close"].iloc[0]
                
                df_eq["Portfolio (Normalized)"] = (df_eq["portfolio_equity"] / first_port) * 100.0
                df_eq["NIFTY 50 (Normalized)"] = (df_eq["nifty_close"] / first_nifty) * 100.0
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_eq["date"], 
                    y=df_eq["Portfolio (Normalized)"], 
                    mode='lines', 
                    name='Indian-Alpha Portfolio',
                    line=dict(color='#00ffcc', width=2.5)
                ))
                fig.add_trace(go.Scatter(
                    x=df_eq["date"], 
                    y=df_eq["NIFTY 50 (Normalized)"], 
                    mode='lines', 
                    name='NIFTY 50 Benchmark',
                    line=dict(color='#ff6666', width=1.5, dash='dash')
                ))
                
                fig.update_layout(
                    title="Systematic Strategy Outperformance Curve",
                    xaxis_title="Simulation Date",
                    yaxis_title="Normalized Value (Baseline = 100)",
                    paper_bgcolor='#0d0d11',
                    plot_bgcolor='#15151e',
                    font=dict(color='#e0e0ea'),
                    xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.03)'),
                    yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.03)'),
                    legend=dict(x=0.01, y=0.99, bgcolor='rgba(13,13,17,0.8)'),
                    margin=dict(l=20, r=20, t=40, b=20),
                    height=450
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Equity curve dataset is empty.")
                
            st.write("---")
            
            # --- 3. RENDER SEARCHABLE TRANSACTION LEDGER ---
            st.subheader("📖 Chronological Backtest Transaction Ledger")
            trades = results.get("trades", [])
            if trades:
                rows = []
                for t in reversed(trades):
                    action = t.get("action", "BUY")
                    pnl = t.get("pnl", 0.0)
                    pnl_pct = t.get("pnl_pct", 0.0)
                    
                    rows.append({
                        "Timestamp": t.get("timestamp", "Unknown"),
                        "Ticker": t.get("symbol", "Unknown"),
                        "Action": "🟢 BUY" if action == "BUY" else "🔴 SELL",
                        "Quantity": t.get("quantity", 0),
                        "Price (₹)": f"{t.get('price', 0.0):,.2f}",
                        "Slippage/Fees (₹)": f"{t.get('brokerage', 0.0):,.2f}",
                        "Net P&L (₹)": f"{pnl:+,.2f}" if action == "SELL" else "—",
                        "Return (%)": f"{pnl_pct:+.2f}%" if action == "SELL" else "—",
                        "Execution Rationale": t.get("reason", "")
                    })
                df_trades = pd.DataFrame(rows)
                st.dataframe(df_trades, use_container_width=True, hide_index=True)
            else:
                st.info("No transaction logs recorded.")
                
            st.write("---")
            if st.button("🔄 Re-Run Historical Simulation (with modified strategy.yaml settings)", use_container_width=True):
                trigger_run = True

    # --- EXECUTE BACKTEST IN Streamlit (Dynamic Loading UI) ---
    if trigger_run:
        st.write("---")
        with st.status("⚡ Running High-Performance Out-of-Sample Strategy Backtest...", expanded=True) as status:
            status.write("Initializing datasets and active strategy configurations...")
            
            # Load active strategy
            strategy_cfg = load_strategy()
            
            # Run using python command in background to prevent blocking streamlit
            import subprocess
            import sys
            
            status.write("Downloading 5 years of daily tickers history for 200 constituents (Caching active)...")
            # Run backtest script
            process = subprocess.Popen(
                [sys.executable, "run_backtest.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for completion and read output
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                status.update(label="🎉 Backtest Simulation Complete!", state="complete", expanded=False)
                st.toast("Backtest completed successfully!", icon="🟢")
                st.rerun()
            else:
                status.update(label="❌ Backtest Simulation Failed!", state="error", expanded=True)
                st.code(stderr, language="text")
