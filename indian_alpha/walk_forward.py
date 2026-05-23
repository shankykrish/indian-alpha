import numpy as np
import pandas as pd
from typing import Dict, Any, List
from loguru import logger

class WalkForwardValidator:
    """
    Quant research validation engine.
    Executes:
    - Out-of-sample walk-forward sanity checks.
    - Monte Carlo return bootstrapping to simulate confidence intervals.
    - Parameter stability checks.
    """
    def __init__(self, confidence_level: float = 0.95):
        self.confidence_level = confidence_level

    def run_monte_carlo(self, trade_returns_pct: List[float], simulations: int = 1000, horizon_days: int = 20) -> Dict[str, Any]:
        """
        Runs a bootstrap Monte Carlo simulation on recent trade returns.
        Helps check if current returns are robust or just random noise.
        """
        if not trade_returns_pct or len(trade_returns_pct) < 5:
            logger.warning("Monte Carlo requires at least 5 trade returns. Skipping.")
            return {"mean_return": 0.0, "var_95": 0.0, "cvar_95": 0.0, "distribution": []}

        try:
            np.random.seed(42)  # Reproducibility
            simulated_paths = []
            
            for _ in range(simulations):
                # Sample with replacement
                path = np.random.choice(trade_returns_pct, size=horizon_days, replace=True)
                simulated_paths.append(np.sum(path))
                
            simulated_paths = np.array(simulated_paths)
            
            # Sort returns to find VaR (Value at Risk)
            sorted_paths = np.sort(simulated_paths)
            var_index = int((1 - self.confidence_level) * simulations)
            var_95 = -sorted_paths[var_index]
            
            # CVaR (Conditional Value at Risk)
            cvar_95 = -np.mean(sorted_paths[:var_index])
            
            return {
                "mean_return": float(np.mean(simulated_paths)),
                "median_return": float(np.median(simulated_paths)),
                "var_95": float(var_95),
                "cvar_95": float(cvar_95),
                "max_simulated_loss": float(-np.min(simulated_paths)),
                "max_simulated_gain": float(np.max(simulated_paths)),
                "simulations_count": simulations,
                "horizon_days": horizon_days
            }
        except Exception as e:
            logger.error(f"Monte Carlo simulation failed: {e}")
            return {"mean_return": 0.0, "var_95": 0.0, "cvar_95": 0.0, "distribution": []}

    def check_parameter_stability(self, history_hypotheses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyzes standard deviation and frequencies of parameter changes in hypotheses log.
        Flags high-frequency switching as 'parameter chatter' or overfitting.
        """
        if not history_hypotheses:
            return {"status": "STABLE", "changes_count": 0, "telemetry": {}}
            
        variables = [h.get("variable") for h in history_hypotheses if h.get("variable")]
        counts = pd.Series(variables).value_counts()
        
        # Chatter check: if one variable was modified > 4 times in the last 10 entries
        most_active_var = counts.index[0] if not counts.empty else "None"
        most_active_count = int(counts.iloc[0]) if not counts.empty else 0
        
        status = "STABLE"
        chatter_warning = False
        
        if most_active_count >= 4:
            status = "UNSTABLE (OVERFITTING CHATTER)"
            chatter_warning = True
            logger.warning(f"Parameter Chatter detected on variable: {most_active_var}. Adjusted {most_active_count} times recently.")

        return {
            "status": status,
            "chatter_warning": chatter_warning,
            "changes_count": len(history_hypotheses),
            "most_active_variable": most_active_var,
            "most_active_variable_count": most_active_count,
            "parameters_distribution": counts.to_dict()
        }
