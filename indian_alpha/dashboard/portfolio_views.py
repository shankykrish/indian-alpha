import streamlit as st
import pandas as pd
from typing import Dict, Any
from indian_alpha.dashboard.charts import draw_sector_concentration

def render_portfolio_panel(portfolio_data: Dict[str, Any]):
    """Renders the portfolio and open paper trade positions overview panel."""
    st.header("💼 Live Paper Portfolio Intelligence")
    
    # 1. Metric Summary Bar
    cash = portfolio_data.get("cash", 1000000.0)
    positions = portfolio_data.get("positions", {})
    equity = portfolio_data.get("total_equity", cash)
    
    # Calculate returns
    initial = 1000000.0
    total_return = ((equity - initial) / initial) * 100.0
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Account Equity", "₹{:,.2f}".format(equity), f"{total_return:+.2f}% vs Initial")
    with col2:
        st.metric("Cash Balance Available", "₹{:,.2f}".format(cash))
    with col3:
        st.metric("Holdings Valuation", "₹{:,.2f}".format(equity - cash))
    with col4:
        st.metric("Active Holdings", f"{len(positions)} Positions")
        
    st.write("---")
    
    # 2. Holdings Table
    st.subheader("📊 Open Simulated Positions")
    if not positions:
        st.info("No open paper positions currently. System is preserving 100% Cash or scanning for momentum candidates.")
    else:
        # Construct positions table
        rows = []
        for symbol, pos in positions.items():
            entry_price = pos["entry_price"]
            current_price = pos["current_price"]
            qty = pos["quantity"]
            mtm_value = qty * current_price
            pnl = pos["unrealized_pnl"]
            pnl_pct = pos["unrealized_pnl_pct"]
            
            rows.append({
                "Ticker Symbol": symbol,
                "Quantity": qty,
                "Entry Price (₹)": f"{entry_price:,.2f}",
                "Mark Price (₹)": f"{current_price:,.2f}",
                "Total Value (₹)": f"{mtm_value:,.2f}",
                "Unrealized P&L (₹)": f"{pnl:+,.2f}",
                "Return (%)": f"{pnl_pct:+.2f}%",
                "Sector Theme": pos.get("sector", "Other")
            })
            
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)
        
    st.write("---")
    
    # 3. Sector Distribution Chart
    st.subheader("🧩 Sector Sizing & Risk Controls")
    if positions:
        fig = draw_sector_concentration(positions)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No active sector concentration to display.")
