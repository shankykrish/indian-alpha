import os
import yaml
from datetime import datetime
from typing import List, Dict, Any, Tuple
from loguru import logger

from indian_alpha.storage.trades import load_trades
from indian_alpha.storage.strategy_store import load_strategy, save_strategy
from indian_alpha.storage.hypotheses import save_hypothesis
from indian_alpha.storage.market_regimes import load_regimes_history

from indian_alpha.config import GOALS_FILE

class SelfLearningReflectionEngine:
    """
    Core cognitive module of the Indian-Alpha platform.
    Evaluates paper trading outcomes, compares them against regime goals,
    formulates evolutionary hypotheses, and modifies EXACTLY ONE variable.
    """
    def __init__(self, goals_path: str = GOALS_FILE):
        self.goals_path = goals_path

    def load_goals(self) -> Dict[str, Any]:
        if not os.path.exists(self.goals_path):
            logger.error(f"Goals configuration not found at {self.goals_path}.")
            return {}
        try:
            with open(self.goals_path, "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Error loading goals from {self.goals_path}: {e}")
            return {}

    def calculate_recent_metrics(self, trades: List[Dict[str, Any]], count: int = 10) -> Dict[str, Any]:
        """Calculates performance metrics for the last N trades."""
        if not trades:
            return {"win_rate": 0.0, "pnl_sum": 0.0, "avg_return": 0.0, "sharpe": 0.0, "max_drawdown": 0.0}
            
        recent = trades[-count:]
        wins = [t for t in recent if t.get("pnl", 0.0) > 0]
        win_rate = len(wins) / len(recent)
        
        pnls = [t.get("pnl", 0.0) for t in recent]
        pnl_pcts = [t.get("pnl_pct", 0.0) for t in recent]
        pnl_sum = sum(pnls)
        avg_return = sum(pnl_pcts) / len(recent)
        
        # Calculate a simple Sharpe ratio
        import numpy as np
        std_ret = np.std(pnl_pcts) if len(pnl_pcts) > 1 else 0.0
        sharpe = (avg_return / std_ret) * np.sqrt(252) if std_ret > 0 else 0.0
        
        # Simple local drawdown calculation
        cum_returns = np.cumsum(pnl_pcts)
        running_max = np.maximum.accumulate(cum_returns)
        drawdowns = running_max - cum_returns
        max_drawdown = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0
        
        return {
            "win_rate": float(win_rate),
            "pnl_sum": float(pnl_sum),
            "avg_return": float(avg_return),
            "sharpe": float(sharpe),
            "max_drawdown": float(max_drawdown),
            "sample_size": len(recent)
        }

    def trigger_reflection(self) -> bool:
        """
        Main entrypoint for the learning loop.
        Evaluates recent trades, detects underperformance or growth opportunities, 
        and adapts one strategy parameter.
        """
        logger.info("Initiating regime-aware reflection cycle...")
        
        # 1. Load data
        trades = load_trades()
        strategy = load_strategy()
        goals_data = self.load_goals()
        regime_history = load_regimes_history()
        
        if not strategy or not goals_data:
            logger.error("Failed to load strategy or goals config. Aborting reflection.")
            return False
            
        cadence = strategy.get("reflection", {}).get("cadence_trades", 10)
        
        # Only reflect when we have at least cadence trades
        if len(trades) < cadence:
            logger.info(f"Insufficient trade history for learning. Have {len(trades)} trades, need at least {cadence}.")
            return False
            
        # 2. Get active market regime
        active_regime = "sideways"
        regime_rationale = "Default fallback"
        if regime_history:
            latest_regime_classification = regime_history[-1]
            active_regime = latest_regime_classification.get("regime", "sideways")
            regime_rationale = latest_regime_classification.get("rationale", "")
            
        logger.info(f"Active Market Regime detected: {active_regime} ({regime_rationale})")
        
        # 3. Retrieve targets for this regime
        regime_targets = goals_data.get("regime_aware_targets", {}).get(active_regime, {})
        if not regime_targets:
            logger.warning(f"No targets defined for regime {active_regime} in goal.yaml. Using default.")
            regime_targets = {"min_win_rate": 0.50, "max_drawdown": 0.10, "min_sharpe": 0.5}
            
        # 4. Calculate actual performance
        actual = self.calculate_recent_metrics(trades, count=cadence)
        logger.info(f"Recent {cadence} Trades Performance: Win Rate: {actual['win_rate']*100:.1f}%, Avg Return: {actual['avg_return']:.2f}%, Sharpe: {actual['sharpe']:.2f}, Max DD: {actual['max_drawdown']:.2f}%")
        logger.info(f"Regime Targets: Win Rate: {regime_targets.get('min_win_rate', 0.5)*100:.1f}%, Sharpe: {regime_targets.get('min_sharpe', 0.5):.2f}, Max DD: {regime_targets.get('max_drawdown', 0.1)*100:.1f}%")
        
        # 5. Compare & generate hypothesis
        hypothesis_triggered = False
        target_variable = ""
        old_val = None
        new_val = None
        hypothesis_msg = ""
        
        # Clone strategy for modification
        modified_strategy = yaml.safe_load(yaml.dump(strategy))
        entry_cfg = modified_strategy.get("entry", {})
        risk_cfg = modified_strategy.get("risk", {})
        
        # Core Optimization Rules (Adapts EXACTLY ONE variable)
        # CASE A: Drawdown exceeds threshold -> Tighten Stop Loss or reduce positions
        if actual["max_drawdown"] > regime_targets.get("max_drawdown", 0.10) * 100.0:
            target_variable = "risk.stop_loss_pct"
            old_val = risk_cfg.get("stop_loss_pct", 7)
            new_val = max(4, old_val - 1)  # Tighten stop loss by 1% (cap at 4%)
            risk_cfg["stop_loss_pct"] = new_val
            hypothesis_msg = f"Drawdown ({actual['max_drawdown']:.2f}%) exceeds target ({regime_targets.get('max_drawdown')*100}%). Tightening stop loss from {old_val}% to {new_val}% to protect capital."
            hypothesis_triggered = True
            
        # CASE B: Win rate is too low -> Increase momentum quality barrier
        elif actual["win_rate"] < regime_targets.get("min_win_rate", 0.50):
            target_variable = "entry.momentum_quality_min"
            old_val = entry_cfg.get("momentum_quality_min", 75)
            new_val = min(90, old_val + 3)  # Increase momentum composite hurdle by 3 points (cap at 90)
            entry_cfg["momentum_quality_min"] = new_val
            hypothesis_msg = f"Win rate ({actual['win_rate']*100:.1f}%) is below target ({regime_targets.get('min_win_rate')*100}%). Raising momentum composite hurdle from {old_val} to {new_val} to screen out low-probability trades."
            hypothesis_triggered = True
            
        # CASE C: Sharpe is low (slippage or weak breakouts) -> Increase volume expansion threshold
        elif actual["sharpe"] < regime_targets.get("min_sharpe", 0.5):
            target_variable = "entry.volume_expansion_ratio"
            old_val = entry_cfg.get("volume_expansion_ratio", 1.8)
            new_val = round(min(3.0, old_val + 0.2), 2)  # Increase volume expansion filter (cap at 3.0x)
            entry_cfg["volume_expansion_ratio"] = new_val
            hypothesis_msg = f"Sharpe ratio ({actual['sharpe']:.2f}) is below target ({regime_targets.get('min_sharpe')}). Raising volume confirmation ratio from {old_val}x to {new_val}x to ensure high-liquidity institutional backing."
            hypothesis_triggered = True
            
        # CASE D: Strategy is highly profitable -> We can safely expand exposure slightly
        elif actual["win_rate"] >= regime_targets.get("min_win_rate", 0.58) and actual["sharpe"] > regime_targets.get("min_sharpe", 1.0):
            # Safe to lower entry hurdle slightly to capture more momentum candidates
            target_variable = "entry.momentum_quality_min"
            old_val = entry_cfg.get("momentum_quality_min", 75)
            if old_val > 65:
                new_val = old_val - 2  # Expand universe access by lowering quality minimum (floor at 65)
                entry_cfg["momentum_quality_min"] = new_val
                hypothesis_msg = f"Excellent performance detected! Win Rate: {actual['win_rate']*100:.1f}%, Sharpe: {actual['sharpe']:.2f}. Lowering momentum quality hurdle from {old_val} to {new_val} to capture additional momentum breakouts."
                hypothesis_triggered = True
                
        # 6. Apply strategy modification
        if hypothesis_triggered:
            # Increment version
            old_version = int(strategy.get("version", "01"))
            new_version = f"{old_version + 1:02d}"
            modified_strategy["version"] = new_version
            
            # Archive previous & save new configuration
            save_strategy(modified_strategy, archive=True)
            
            # Log hypothesis
            hypothesis_record = {
                "timestamp": datetime.now().isoformat(),
                "regime": active_regime,
                "strategy_version_from": strategy.get("version"),
                "strategy_version_to": new_version,
                "variable": target_variable,
                "old_value": old_val,
                "new_value": new_val,
                "performance_telemetry": actual,
                "regime_targets": regime_targets,
                "hypothesis": hypothesis_msg
            }
            save_hypothesis(hypothesis_record)
            return True
            
        logger.info("Reflection complete. Performance aligns with regime targets. No strategy modifications required.")
        return False
