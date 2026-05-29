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
        st.write(f"- High Breakout Period Lookback: **{entry.get('breakout_period', 20)} Days**")
        st.write(f"- Volume Expansion Ratio Multiplier: **{entry.get('volume_expansion_ratio')}x**")
        st.write(f"- Delivery Volume Expansion Multiplier: **{entry.get('delivery_volume_ratio')}x**")
        st.write(f"- Minimum Entry RSI-14: **{entry.get('rsi_min')}**")
        st.write(f"- Minimum Composite Momentum Quality: **{entry.get('momentum_quality_min')} / 100**")
        
    with col2:
        st.subheader("🛡️ Portfolio Risk Management Rules")
        risk = strategy_cfg.get("risk", {})
        
        # Dynamic Initial Stop Loss display
        sl_mode = risk.get('stop_loss_mode', 'fixed')
        if sl_mode == 'atr':
            st.write(f"- Initial Stop Loss: **{risk.get('atr_stop_multiplier', 2.5)}x ATR(14)** (Dynamic)")
        else:
            st.write(f"- Initial Stop Loss: **-{risk.get('stop_loss_pct', 7.0)}%** (Fixed)")
            
        # Dynamic Trailing Stop display
        ts_mode = risk.get('trailing_stop_mode', 'atr')
        if ts_mode == 'atr':
            st.write(f"- Trailing Stop: **{risk.get('atr_trailing_multiplier', 3.0)}x ATR(14)** (Dynamic)")
        elif ts_mode == 'fixed':
            st.write(f"- Trailing Stop: **-{risk.get('trailing_stop_pct', 15.0)}%** (Fixed)")
        else:
            st.write("- Trailing Stop: **Disabled**")
            
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
