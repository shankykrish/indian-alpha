import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from typing import List, Dict, Any, Optional

def create_dark_layout(fig: go.Figure, title: str, xaxis_title: str = "", yaxis_title: str = "") -> go.Figure:
    """Applies a premium, highly aesthetic dark-mode layout to any Plotly figure."""
    fig.update_layout(
        title={
            'text': title,
            'y':0.95,
            'x':0.5,
            'xanchor': 'center',
            'yanchor': 'top',
            'font': {'size': 20, 'color': '#ffffff', 'family': 'Outfit, Inter, sans-serif'}
        },
        paper_bgcolor='rgba(15,15,20,1)', # sleek glassmorphism base
        plot_bgcolor='rgba(25,25,35,1)',
        xaxis=dict(
            title=xaxis_title,
            gridcolor='rgba(255,255,255,0.05)',
            zerolinecolor='rgba(255,255,255,0.1)',
            tickfont=dict(color='#a0a0b0')
        ),
        yaxis=dict(
            title=yaxis_title,
            gridcolor='rgba(255,255,255,0.05)',
            zerolinecolor='rgba(255,255,255,0.1)',
            tickfont=dict(color='#a0a0b0')
        ),
        font=dict(color='#ffffff'),
        legend=dict(
            bgcolor='rgba(10,10,15,0.8)',
            bordercolor='rgba(255,255,255,0.1)',
            tickfont=dict(color='#ffffff')
        ),
        margin=dict(l=40, r=40, t=60, b=40)
    )
    return fig

def draw_equity_curve(portfolio_history: List[Dict[str, Any]]) -> go.Figure:
    """Draws a premium glowing equity curve over time."""
    fig = go.Figure()
    if not portfolio_history:
        # Dummy chart
        fig.add_trace(go.Scatter(x=[0], y=[1000000.0], mode="lines+markers", name="Equity"))
        return create_dark_layout(fig, "No Portfolio History Available")
        
    df = pd.DataFrame(portfolio_history)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    
    # Glowing equity curve line
    fig.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df["total_equity"],
        mode="lines",
        name="Total Equity",
        line=dict(color='#00ffcc', width=3),
        fill='tozeroy',
        fillcolor='rgba(0, 255, 204, 0.05)'
    ))
    
    return create_dark_layout(fig, "Portfolio Equity Growth (Mark-to-Market)", "Timeline", "Equity (₹)")

def draw_drawdown_curve(portfolio_history: List[Dict[str, Any]]) -> go.Figure:
    """Draws peak-to-trough drawdowns over time."""
    fig = go.Figure()
    if not portfolio_history:
        return create_dark_layout(fig, "No Drawdown History")
        
    df = pd.DataFrame(portfolio_history)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    
    # Calculate drawdowns
    equity = df["total_equity"]
    peaks = equity.cummax()
    dds = ((equity - peaks) / peaks) * 100.0
    
    fig.add_trace(go.Scatter(
        x=df["timestamp"],
        y=dds,
        mode="lines",
        name="Drawdown %",
        line=dict(color='#ff3366', width=2),
        fill='tozeroy',
        fillcolor='rgba(255, 51, 102, 0.08)'
    ))
    
    return create_dark_layout(fig, "Historical Drawdown %", "Timeline", "Decline (%)")

def draw_regime_donut(regime_history: List[Dict[str, Any]]) -> go.Figure:
    """Renders classified regime frequency metrics in a premium donut chart."""
    if not regime_history:
        fig = go.Figure()
        return create_dark_layout(fig, "No Regime History")
        
    df = pd.DataFrame(regime_history)
    counts = df["regime"].value_counts()
    
    colors = {
        "bull_low_vol": "#00ffcc",
        "bull_high_vol": "#00ccff",
        "sideways": "#ffcc00",
        "recovery": "#99ff33",
        "bear": "#ff6600",
        "panic": "#ff3366"
    }
    
    fig = go.Figure(data=[go.Pie(
        labels=counts.index,
        values=counts.values,
        hole=.5,
        marker=dict(colors=[colors.get(k, "#a0a0b0") for k in counts.index])
    )])
    
    return create_dark_layout(fig, "System Regime Exposure Distribution")

def draw_sector_concentration(positions: Dict[str, Dict[str, Any]]) -> go.Figure:
    """Draws active capital allocated per industry sector."""
    fig = go.Figure()
    if not positions:
        return create_dark_layout(fig, "No Open Holdings")
        
    sector_values = {}
    for sym, pos in positions.items():
        sec = pos.get("sector", "Other")
        val = pos["quantity"] * pos["current_price"]
        sector_values[sec] = sector_values.get(sec, 0.0) + val
        
    df = pd.DataFrame(list(sector_values.items()), columns=["Sector", "Value"])
    
    fig = go.Figure(data=[go.Bar(
        x=df["Sector"],
        y=df["Value"],
        marker_color='#6633ff',
        text=["₹{:,.2f}".format(v) for v in df["Value"]],
        textposition='auto'
    )])
    
    return create_dark_layout(fig, "Sector Concentration & Exposure Analysis", "Sector Themes", "Allocated Value (₹)")

def draw_parameter_evolution(hypotheses: List[Dict[str, Any]], variable_name: str) -> go.Figure:
    """Plots the learning parameter updates over time."""
    fig = go.Figure()
    # Filter hypotheses containing this variable
    var_hyps = [h for h in hypotheses if h.get("variable") == variable_name]
    if not var_hyps:
        return create_dark_layout(fig, f"No evolutionary logs for {variable_name}")
        
    df = pd.DataFrame(var_hyps)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    
    fig.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df["new_value"],
        mode="lines+markers",
        name=variable_name,
        line=dict(color='#ffaa00', width=2),
        marker=dict(size=8, color='#ff6600')
    ))
    
    return create_dark_layout(fig, f"Cognitive Evolution: {variable_name}", "Learning Steps Timeline", "Value")
