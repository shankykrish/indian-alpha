import pandas as pd
from typing import Dict, Any, List, Optional
from loguru import logger
import os
import pytz
from datetime import datetime, time

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
            low = df["low"]
            
            last_close = close.iloc[-1]
            prev_close = close.iloc[-2]
            
            # Load parameters from strategy.yaml config
            entry_config = self.config.get("entry", {})
            
            # --- PRE-FILTER: Market Cap Screener ---
            market_cap_cr = float(fundamentals.get("market_cap", 0.0) / 10000000.0)
            min_market_cap_cr = entry_config.get("min_market_cap_cr", 0.0)
            if min_market_cap_cr > 0.0 and market_cap_cr < min_market_cap_cr:
                return {"action": "HOLD", "price": 0.0, "reason": f"Market cap (Rs. {market_cap_cr:.2f} Cr) below minimum threshold (Rs. {min_market_cap_cr:.2f} Cr)"}

            # --- PRE-FILTER: Average Daily Turnover Screener ---
            avg_vol_20d = volume.iloc[-20:].mean()
            avg_close_20d = close.iloc[-20:].mean()
            avg_turnover_cr = (avg_vol_20d * avg_close_20d) / 10000000.0
            min_turnover_cr = entry_config.get("min_daily_turnover_cr", 0.0)
            if min_turnover_cr > 0.0 and avg_turnover_cr < min_turnover_cr:
                return {"action": "HOLD", "price": 0.0, "reason": f"Average daily turnover (Rs. {avg_turnover_cr:.2f} Cr) below threshold (Rs. {min_turnover_cr:.2f} Cr)"}

            # --- RULE 1: Above Moving Averages ---
            ma_50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else last_close
            ma_200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else last_close
            
            if entry_config.get("above_50dma", True) and last_close < ma_50:
                return {"action": "HOLD", "price": 0.0, "reason": f"Close ({last_close:.2f}) below 50 DMA ({ma_50:.2f})"}
            if entry_config.get("above_200dma", True) and last_close < ma_200:
                return {"action": "HOLD", "price": 0.0, "reason": f"Close ({last_close:.2f}) below 200 DMA ({ma_200:.2f})"}
                
            # --- RULE 2: High Breakout ---
            breakout_period = entry_config.get("breakout_period", 20)
            if breakout_period > 0:
                high_n = high.iloc[-(breakout_period + 1):-1].max() # Exclude current bar to detect crossing
                if last_close <= high_n:
                    return {"action": "HOLD", "price": 0.0, "reason": f"Price ({last_close:.2f}) did not break {breakout_period}-day high ({high_n:.2f})"}

            # Calculate dynamic volume scale factor based on elapsed time of the trading day
            # Market is active from 09:15 to 15:30 IST (375 minutes)
            is_fast_run = os.getenv("FAST_RUN", "false").lower() == "true"
            now_ist = datetime.now(pytz.timezone("Asia/Kolkata"))
            
            if is_fast_run or now_ist.strftime("%A") in ["Saturday", "Sunday"] or now_ist.time() >= time(15, 20):
                fraction = 1.0
            elif now_ist.time() <= time(9, 15):
                fraction = 0.05
            else:
                market_start = datetime.combine(now_ist.date(), time(9, 15))
                market_start = pytz.timezone("Asia/Kolkata").localize(market_start)
                elapsed_minutes = (now_ist - market_start).total_seconds() / 60.0
                fraction = min(1.0, max(0.05, elapsed_minutes / 375.0))

            # --- RULE 3: Volume Expansion Ratio ---
            vol_expansion = volume.iloc[-1] / avg_vol_20d if avg_vol_20d > 0 else 1.0
            raw_min_vol_exp = entry_config.get("volume_expansion_ratio", 1.8)
            min_vol_exp = raw_min_vol_exp * fraction
            if vol_expansion < min_vol_exp:
                return {"action": "HOLD", "price": 0.0, "reason": f"Volume expansion {vol_expansion:.2f}x below scaled threshold {min_vol_exp:.2f}x (Raw: {raw_min_vol_exp}x, Fraction: {fraction:.2f})"}

            # --- RULE 4: Delivery Volume Ratio ---
            del_pct = df.get("delivery_pct", pd.Series([0.4] * len(df))).iloc[-1]
            del_expansion = (volume.iloc[-1] * del_pct) / (avg_vol_20d * 0.4) if avg_vol_20d > 0 else 1.0
            raw_min_del_exp = entry_config.get("delivery_volume_ratio", 1.5)
            min_del_exp = raw_min_del_exp * fraction
            if del_expansion < min_del_exp:
                return {"action": "HOLD", "price": 0.0, "reason": f"Delivery volume expansion {del_expansion:.2f}x below scaled threshold {min_del_exp:.2f}x (Raw: {raw_min_del_exp}x, Fraction: {fraction:.2f})"}

            # --- RULE 5: Relative Strength vs Nifty & Sector ---
            if rankings_entry:
                factors = rankings_entry.get("factors", {})
                rs_nifty = factors.get("rs_vs_nifty", 0.0)
                rs_sector = factors.get("rs_vs_sector", 0.0)
                comp_score = rankings_entry.get("composite_score", 0.0)
                
                min_rs_nifty = entry_config.get("relative_strength_vs_nifty_min", 70)
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

            # Calculate ATR for stop losses
            try:
                high_low = high - low
                high_close = (high - close.shift()).abs()
                low_close = (low - close.shift()).abs()
                ranges = pd.concat([high_low, high_close, low_close], axis=1)
                true_range = ranges.max(axis=1)
                atr_series = true_range.rolling(14).mean()
                atr_value = float(atr_series.iloc[-1])
                if pd.isna(atr_value) or atr_value <= 0.0:
                    atr_value = float(last_close * 0.03)
            except Exception as e:
                logger.warning(f"Error calculating ATR for {symbol}: {e}")
                atr_value = float(last_close * 0.03)

            return {
                "action": "BUY",
                "price": float(last_close),
                "atr_value": atr_value,
                "reason": f"Valid momentum breakout! RSI: {rsi:.1f}, Vol Exp: {vol_expansion:.1f}x, Theme: {fundamentals.get('theme')}"
            }
            
        except Exception as e:
            logger.error(f"Error generating momentum breakout signal for {symbol}: {e}")
            return {"action": "HOLD", "price": 0.0, "reason": f"Calculation error: {e}"}
