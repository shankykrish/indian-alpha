import pandas as pd
from typing import Dict, Any, List, Optional
from loguru import logger

class MomentumBreakoutStrategy:
    """
    Implements the Primary Momentum Breakout Strategy using parameters from strategy.yaml.
    Specifically scans for PSU, defense, capital goods, and smallcap breakouts.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def generate_signals(
        self, 
        df: pd.DataFrame, 
        fundamentals: Dict[str, Any], 
        rankings_entry: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluates rules for a single stock and generates a entry/exit signal.
        Returns:
            {"action": "BUY"/"SELL"/"HOLD", "price": float, "reason": str}
        """
        symbol = fundamentals.get("symbol")
        if df.empty or len(df) < 50:
            return {"action": "HOLD", "price": 0.0, "reason": "Insufficient history"}

        try:
            close = df["close"]
            volume = df["volume"]
            high = df["high"]
            
            last_close = close.iloc[-1]
            prev_close = close.iloc[-2]
            
            # Load parameters from strategy.yaml config
            entry_config = self.config.get("entry", {})
            
            # --- RULE 1: Above Moving Averages ---
            ma_50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else last_close
            ma_200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else last_close
            
            if entry_config.get("above_50dma", True) and last_close < ma_50:
                return {"action": "HOLD", "price": 0.0, "reason": f"Close ({last_close:.2f}) below 50 DMA ({ma_50:.2f})"}
            if entry_config.get("above_200dma", True) and last_close < ma_200:
                return {"action": "HOLD", "price": 0.0, "reason": f"Close ({last_close:.2f}) below 200 DMA ({ma_200:.2f})"}
                
            # --- RULE 2: Breakout 20-day high ---
            if entry_config.get("breakout_20d", True):
                high_20d = high.iloc[-21:-1].max() # Exclude current bar to detect crossing
                if last_close <= high_20d:
                    return {"action": "HOLD", "price": 0.0, "reason": f"Price ({last_close:.2f}) did not break 20-day high ({high_20d:.2f})"}

            # --- RULE 3: Volume Expansion Ratio ---
            avg_vol_20d = volume.iloc[-20:].mean()
            vol_expansion = volume.iloc[-1] / avg_vol_20d if avg_vol_20d > 0 else 1.0
            min_vol_exp = entry_config.get("volume_expansion_ratio", 1.8)
            if vol_expansion < min_vol_exp:
                return {"action": "HOLD", "price": 0.0, "reason": f"Volume expansion {vol_expansion:.2f}x below threshold {min_vol_exp}x"}

            # --- RULE 4: Delivery Volume Ratio ---
            del_pct = df.get("delivery_pct", pd.Series([0.4] * len(df))).iloc[-1]
            del_expansion = (volume.iloc[-1] * del_pct) / (avg_vol_20d * 0.4) if avg_vol_20d > 0 else 1.0
            min_del_exp = entry_config.get("delivery_volume_ratio", 1.5)
            if del_expansion < min_del_exp:
                return {"action": "HOLD", "price": 0.0, "reason": f"Delivery volume expansion {del_expansion:.2f}x below threshold {min_del_exp}x"}

            # --- RULE 5: Relative Strength vs Nifty & Sector ---
            if rankings_entry:
                factors = rankings_entry.get("factors", {})
                rs_nifty = factors.get("rs_vs_nifty", 0.0)
                rs_sector = factors.get("rs_vs_sector", 0.0)
                comp_score = rankings_entry.get("composite_score", 0.0)
                
                min_rs_nifty = entry_config.get("relative_strength_vs_nifty_min", 70)
                # Map raw relative strength return difference to an index range or compare directly
                # If the composite ranking score represents momentum quality:
                min_quality = entry_config.get("momentum_quality_min", 75)
                
                if comp_score < min_quality:
                    return {"action": "HOLD", "price": 0.0, "reason": f"Composite momentum score {comp_score:.2f} below threshold {min_quality}"}

            # --- RULE 6: RSI momentum check ---
            # Basic RSI-14 calculation
            delta = close.diff().dropna()
            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)
            avg_gain = gain.rolling(14).mean().iloc[-1]
            avg_loss = loss.rolling(14).mean().iloc[-1]
            rs = avg_gain / avg_loss if avg_loss > 0 else 999.0
            rsi = 100.0 - (100.0 / (1.0 + rs))
            
            min_rsi = entry_config.get("rsi_min", 60)
            if rsi < min_rsi:
                return {"action": "HOLD", "price": 0.0, "reason": f"RSI-14 ({rsi:.2f}) below minimum momentum RSI ({min_rsi})"}

            return {
                "action": "BUY",
                "price": float(last_close),
                "reason": f"Valid momentum breakout! RSI: {rsi:.1f}, Vol Exp: {vol_expansion:.1f}x, Theme: {fundamentals.get('theme')}"
            }
            
        except Exception as e:
            logger.error(f"Error generating momentum breakout signal for {symbol}: {e}")
            return {"action": "HOLD", "price": 0.0, "reason": f"Calculation error: {e}"}
