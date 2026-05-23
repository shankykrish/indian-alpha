import streamlit as st
import pandas as pd
from typing import List, Dict, Any
from indian_alpha.dashboard.charts import draw_parameter_evolution

def render_reflection_panel(hypotheses: List[Dict[str, Any]]):
    """Renders the cognitive evolution history and hypotheses updates logged by the self-learning reflection engine."""
    st.header("🧠 Self-Learning Reflection & Cognition Panel")
    
    if not hypotheses:
        st.info("No learning hypotheses logged yet. Reflection will trigger when trade counts reach the required cadence.")
        return
        
    st.write(f"**Cognitive Updates Completed:** {len(hypotheses)} Strategy Adjustments")
    
    # 1. Parameter Evolution Selectbox & Plotly Chart
    st.subheader("📈 Strategy Parameter Evolution Over Time")
    
    variables = list(set([h.get("variable") for h in hypotheses if h.get("variable")]))
    if variables:
        selected_var = st.selectbox("Select Parameter to Trace Evolution", variables)
        fig = draw_parameter_evolution(hypotheses, selected_var)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No numerical parameter changes tracked.")
        
    st.write("---")
    
    # 2. Hypothesis Log Table
    st.subheader("📝 Chronological Evolutionary Hypothesis Journal")
    
    rows = []
    for h in reversed(hypotheses):
        perf = h.get("performance_telemetry", {})
        rows.append({
            "Timestamp": h.get("timestamp", "Unknown"),
            "Market Regime": h.get("regime", "Unknown").upper(),
            "Adjusted Parameter": h.get("variable", "Unknown"),
            "Old Value": f"{h.get('old_value')}",
            "New Value": f"{h.get('new_value')}",
            "Win Rate (%)": f"{perf.get('win_rate', 0.0)*100:.1f}%",
            "Sharpe Ratio": f"{perf.get('sharpe', 0.0):.2f}",
            "Hypothesis & Rationale": h.get("hypothesis", "")
        })
        
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
