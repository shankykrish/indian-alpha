import streamlit as st
import pandas as pd
from typing import Dict, Any
from indian_alpha.dashboard.charts import draw_sector_concentration

def render_portfolio_panel(portfolio_data: Dict[str, Any]):
    """Renders the portfolio and open paper trade positions overview panel."""
    st.header("💼 Live Paper Portfolio Intelligence")
    
    # 1. Metric Summary Bar
    cash = portfolio_data.get("cash")
    if cash is None:
        cash = 1000000.0
        
    positions = portfolio_data.get("positions")
    if positions is None:
        positions = {}
    else:
        import copy
        positions = copy.deepcopy(positions)
        
    # Asynchronously fetch live prices for all positions to show up-to-the-second data in the dashboard
    if positions:
        try:
            import asyncio
            from indian_alpha.providers.yahoo import YahooFinanceProvider
            provider = YahooFinanceProvider()
            
            async def fetch_all_quotes():
                tasks = [provider.fetch_quote(sym) for sym in positions.keys()]
                return await asyncio.gather(*tasks, return_exceptions=True)
                
            quotes = asyncio.run(fetch_all_quotes())
            for i, symbol in enumerate(positions.keys()):
                quote = quotes[i]
                if quote and not isinstance(quote, Exception):
                    price = quote.get("price")
                    if price and price > 0.0:
                        positions[symbol]["current_price"] = price
        except Exception as e:
            pass
            
    # Calculate live equity and valuations based on the latest real-time prices
    positions_value = 0.0
    for symbol, pos in positions.items():
        qty = pos.get("quantity") or 0
        current_price = pos.get("current_price") or pos.get("entry_price") or 0.0
        positions_value += qty * current_price
        
    equity = cash + positions_value
    
    # Calculate returns
    initial = 1000000.0
    try:
        total_return = ((equity - initial) / initial) * 100.0
    except Exception:
        total_return = 0.0
        
    holdings_valuation = positions_value
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Account Equity", "₹{:,.2f}".format(equity), f"{total_return:+.2f}% vs Initial")
    with col2:
        st.metric("Cash Balance Available", "₹{:,.2f}".format(cash))
    with col3:
        st.metric("Holdings Valuation", "₹{:,.2f}".format(holdings_valuation))
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
            entry_price = pos.get("entry_price")
            if entry_price is None:
                entry_price = 0.0
            current_price = pos.get("current_price")
            if current_price is None or current_price == 0.0:
                current_price = entry_price
            qty = pos.get("quantity")
            if qty is None:
                qty = 0
                
            mtm_value = qty * current_price
            
            pnl = pos.get("unrealized_pnl")
            if pnl is None or pnl == 0.0:
                pnl = (current_price - entry_price) * qty
            pnl_pct = pos.get("unrealized_pnl_pct")
            if pnl_pct is None or pnl_pct == 0.0:
                pnl_pct = (((current_price - entry_price) / entry_price) * 100.0) if entry_price > 0.0 else 0.0
            
            rows.append({
                "Ticker Symbol": symbol,
                "Quantity": qty,
                "Entry Price (₹)": f"{entry_price:,.2f}",
                "Mark Price (₹)": f"{current_price:,.2f}",
                "Total Value (₹)": f"{mtm_value:,.2f}",
                "Unrealized P&L (₹)": f"{pnl:+,.2f}",
                "Return (%)": f"{pnl_pct:+.2f}%",
                "Sector Theme": pos.get("sector") or "Other"
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
