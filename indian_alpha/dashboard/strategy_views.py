import streamlit as st
import yaml
from typing import Dict, Any

def render_strategy_panel(strategy_cfg: Dict[str, Any]):
    """Displays the active configuration parameters and strategy settings from strategy.yaml."""
    st.header("⚙️ Active Strategy Configuration")
    
    if not strategy_cfg:
        st.warning("No strategy config found. Check that strategy.yaml is populated.")
        return
        
    st.write(f"**Strategy Type:** `{strategy_cfg.get('strategy_type', 'momentum_breakout').upper()}` | **Active Version:** `v{strategy_cfg.get('version', '01')}`")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📥 Momentum Entry Hurdle Rules")
        entry = strategy_cfg.get("entry", {})
        st.write(f"- Minimum Relative Strength vs Nifty: **{entry.get('relative_strength_vs_nifty_min')}%**")
        st.write(f"- Minimum Relative Strength vs Sector: **{entry.get('relative_strength_vs_sector_min')}%**")
        st.write(f"- 20-Day High Breakout Required: **{entry.get('breakout_20d')}**")
        st.write(f"- Volume Expansion Ratio Multiplier: **{entry.get('volume_expansion_ratio')}x**")
        st.write(f"- Delivery Volume Expansion Multiplier: **{entry.get('delivery_volume_ratio')}x**")
        st.write(f"- Minimum Entry RSI-14: **{entry.get('rsi_min')}**")
        st.write(f"- Minimum Composite Momentum Quality: **{entry.get('momentum_quality_min')} / 100**")
        
    with col2:
        st.subheader("🛡️ Portfolio Risk Management Rules")
        risk = strategy_cfg.get("risk", {})
        st.write(f"- Hard Stop Loss Percentage: **-{risk.get('stop_loss_pct')}%**")
        st.write(f"- Trailing Profit Stop Percentage: **{risk.get('trailing_stop_pct')}%**")
        st.write(f"- Maximum Account Positions Count: **{risk.get('max_positions')}**")
        st.write(f"- Sizing Percentage per Position: **{risk.get('position_size_pct')}%**")
        
        st.subheader("💡 Learning Loop Settings")
        ref = strategy_cfg.get("reflection", {})
        st.write(f"- Evaluation Window: **{ref.get('cadence_trades')} Trades**")
        st.write(f"- Adjust exactly one parameter: **{ref.get('one_variable_only')}**")
        
    st.write("---")
    
    # Raw YAML display
    st.subheader("📝 Active Configuration Code (strategy.yaml)")
    st.code(yaml.safe_dump(strategy_cfg, default_flow_style=False), language="yaml")
