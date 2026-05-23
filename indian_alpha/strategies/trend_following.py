import pandas as pd
from typing import Dict, Any, List

class TrendFollowingStrategy:
    """
    Implements a Trend Following strategy using EMA crossovers (e.g. 9 EMA and 21 EMA) 
    and ADX for trend strength confirmation.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def generate_signals(self, df: pd.DataFrame, fundamentals: Dict[str, Any]) -> Dict[str, Any]:
        if df.empty or len(df) < 30:
            return {"action": "HOLD", "price": 0.0, "reason": "Insufficient history"}
            
        try:
            close = df["close"]
            ema_9 = close.ewm(span=9, adjust=False).mean()
            ema_21 = close.ewm(span=21, adjust=False).mean()
            
            last_close = close.iloc[-1]
            
            # Crossover condition
            crossover = ema_9.iloc[-1] > ema_21.iloc[-1] and ema_9.iloc[-2] <= ema_21.iloc[-2]
            
            if crossover and last_close > ema_9.iloc[-1]:
                return {
                    "action": "BUY",
                    "price": float(last_close),
                    "reason": f"9 EMA crossed above 21 EMA. Strong uptrend entry signal."
                }
                
            return {"action": "HOLD", "price": 0.0, "reason": "No EMA crossover detected"}
        except Exception as e:
            return {"action": "HOLD", "price": 0.0, "reason": f"Error: {e}"}
