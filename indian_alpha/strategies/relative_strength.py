import pandas as pd
from typing import Dict, Any, List

class RelativeStrengthStrategy:
    """
    Implements a Relative Strength Strategy that selects stocks based on their 
    outperformance relative to the NIFTY 50 benchmark index.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def generate_signals(
        self, 
        df: pd.DataFrame, 
        nifty_df: pd.DataFrame,
        fundamentals: Dict[str, Any]
    ) -> Dict[str, Any]:
        if df.empty or nifty_df.empty or len(df) < 50:
            return {"action": "HOLD", "price": 0.0, "reason": "Insufficient history"}
            
        try:
            close = df["close"]
            nifty_close = nifty_df["close" if "close" in nifty_df.columns else nifty_df.columns[0]]
            
            # Align dates
            common = df.index.intersection(nifty_df.index)
            if len(common) < 20:
                return {"action": "HOLD", "price": 0.0, "reason": "Date alignment mismatch"}
                
            last_close = close.loc[common].iloc[-1]
            
            # Calculate 30-day relative strength
            stock_ret = (close.loc[common].iloc[-1] - close.loc[common].iloc[-30]) / close.loc[common].iloc[-30]
            nifty_ret = (nifty_close.loc[common].iloc[-1] - nifty_close.loc[common].iloc[-30]) / nifty_close.loc[common].iloc[-30]
            rs_score = (stock_ret - nifty_ret) * 100.0
            
            if rs_score > 8.0 and last_close > close.loc[common].rolling(20).mean().iloc[-1]:
                return {
                    "action": "BUY",
                    "price": float(last_close),
                    "reason": f"Strong relative strength outperformance: {rs_score:.2f}% above NIFTY over last 30 days."
                }
                
            return {"action": "HOLD", "price": 0.0, "reason": f"RS score {rs_score:.2f}% below buy threshold."}
        except Exception as e:
            return {"action": "HOLD", "price": 0.0, "reason": f"Error: {e}"}
