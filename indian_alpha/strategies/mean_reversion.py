import pandas as pd
from typing import Dict, Any, List

class MeanReversionStrategy:
    """
    Implements a Bollinger Band Mean Reversion strategy.
    Optimized for high-liquidity stocks during Bear or Sideways market regimes.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def generate_signals(self, df: pd.DataFrame, fundamentals: Dict[str, Any]) -> Dict[str, Any]:
        if df.empty or len(df) < 20:
            return {"action": "HOLD", "price": 0.0, "reason": "Insufficient history"}
            
        try:
            close = df["close"]
            last_close = close.iloc[-1]
            
            # Bollinger Bands (20 periods, 2 StdDev)
            ma_20 = close.rolling(20).mean()
            std_20 = close.rolling(20).std()
            lower_band = ma_20 - 2 * std_20
            
            # Entry condition: Price closes below lower Bollinger Band
            oversold = last_close < lower_band.iloc[-1]
            
            # RSI check
            delta = close.diff().dropna()
            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)
            avg_gain = gain.rolling(14).mean().iloc[-1]
            avg_loss = loss.rolling(14).mean().iloc[-1]
            rs = avg_gain / avg_loss if avg_loss > 0 else 999.0
            rsi = 100.0 - (100.0 / (1.0 + rs))
            
            if oversold and rsi < 30.0:
                return {
                    "action": "BUY",
                    "price": float(last_close),
                    "reason": f"Bollinger Band Mean Reversion buy signal! Price below lower band, RSI oversold ({rsi:.1f})."
                }
                
            return {"action": "HOLD", "price": 0.0, "reason": "Not in oversold Bollinger Band range"}
        except Exception as e:
            return {"action": "HOLD", "price": 0.0, "reason": f"Error: {e}"}
