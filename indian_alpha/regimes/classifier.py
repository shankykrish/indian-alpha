import pandas as pd
from typing import Dict, Any, List
from datetime import datetime, timedelta
from loguru import logger

from indian_alpha.providers.base import MarketDataProvider
from indian_alpha.regimes.volatility_regime import calculate_rolling_volatility
from indian_alpha.regimes.breadth_regime import classify_breadth_state
from indian_alpha.regimes.sector_rotation import calculate_sector_momentum, get_sector_rankings

class MarketRegimeClassifier:
    """
    Classifies the Indian equity market into one of 6 core regimes:
    - bull_low_vol
    - bull_high_vol
    - sideways
    - bear
    - panic
    - recovery
    """
    def __init__(self, provider: MarketDataProvider):
        self.provider = provider

    async def classify_regime(self) -> Dict[str, Any]:
        """
        Runs multiple multi-factor data fetches and returns the active classified regime
        along with complete statistical telemetry.
        """
        now = datetime.now()
        start_date = (now - timedelta(days=250)).strftime("%Y-%m-%d")
        end_date = now.strftime("%Y-%m-%d")

        try:
            # 1. Fetch NIFTY 50 index data
            nifty_df = await self.provider.fetch_index_data("NIFTY50", start_date, end_date)
            if nifty_df.empty:
                logger.error("Could not fetch NIFTY 50 index data for regime classification. Using default baseline.")
                return self._default_regime("Nifty Empty")

            close_col = "close" if "close" in nifty_df.columns else nifty_df.columns[0]
            close_series = nifty_df[close_col]
            last_close = close_series.iloc[-1]
            
            # MAs
            ma_50 = close_series.rolling(50).mean().iloc[-1]
            ma_200 = close_series.rolling(200).mean().iloc[-1]
            
            # Trend signals
            in_uptrend = last_close > ma_50 and ma_50 > ma_200
            in_downtrend = last_close < ma_50 and ma_50 < ma_200
            
            # 2. Fetch Volatility (India VIX)
            vix = await self.provider.fetch_vix()
            
            # 3. Fetch Market Breadth
            breadth = await self.provider.fetch_market_breadth()
            breadth_state = classify_breadth_state(breadth)
            
            # 4. Fetch Sector Rotation
            sectors = await self.provider.fetch_sector_data()
            sector_scores = calculate_sector_momentum(sectors)
            top_sectors = get_sector_rankings(sector_scores)
            
            # 5. Fetch Smallcap participation (proxy using NIFTY_SMALLCAP_250 vs NIFTY50)
            smallcap_df = await self.provider.fetch_index_data("NIFTY_SMALLCAP_250", start_date, end_date)
            smallcap_ratio = 1.0
            if not smallcap_df.empty and len(smallcap_df) >= 20:
                sc_close = smallcap_df["close" if "close" in smallcap_df.columns else smallcap_df.columns[0]]
                sc_ret_20d = ((sc_close.iloc[-1] - sc_close.iloc[-20]) / sc_close.iloc[-20]) * 100.0
                nifty_ret_20d = ((close_series.iloc[-1] - close_series.iloc[-20]) / close_series.iloc[-20]) * 100.0
                smallcap_ratio = sc_ret_20d - nifty_ret_20d
                
            # --- REGIME RULES SYSTEM ---
            regime = "sideways"
            rationale = "Market is in range or flat moving averages."
            
            if vix >= 23.0:
                regime = "panic"
                rationale = f"India VIX is highly elevated at {vix:.2f}, indicating intense capitulation/panic selling."
            elif last_close < ma_200 and vix >= 17.0:
                regime = "bear"
                rationale = f"Nifty ({last_close:.2f}) is below 200 DMA ({ma_200:.2f}) with elevated volatility (VIX: {vix:.2f})."
            elif last_close > ma_50 and ma_50 < ma_200 and breadth["pct_above_50dma"] > 55.0:
                regime = "recovery"
                rationale = "Nifty has reclaimed the 50 DMA; breadth is strong; recovering from bearish regime."
            elif in_uptrend:
                if vix < 13.5:
                    regime = "bull_low_vol"
                    rationale = f"Clean uptrend (Nifty > 50 > 200 DMA) with low systemic risk (VIX: {vix:.2f})."
                else:
                    regime = "bull_high_vol"
                    rationale = f"Strong momentum/uptrend, but accompanied by higher systemic volatility (VIX: {vix:.2f})."
            elif last_close < ma_50 and last_close > ma_200:
                regime = "sideways"
                rationale = "Nifty pulled back below 50 DMA but is still holding above the long-term 200 DMA."
                
            classified_data = {
                "timestamp": datetime.now().isoformat(),
                "regime": regime,
                "rationale": rationale,
                "telemetry": {
                    "nifty_close": float(last_close),
                    "nifty_50ma": float(ma_50),
                    "nifty_200ma": float(ma_200),
                    "india_vix": float(vix),
                    "breadth": breadth,
                    "breadth_state": breadth_state,
                    "smallcap_outperformance_20d": float(smallcap_ratio),
                    "top_sector": top_sectors[0] if top_sectors else "None",
                    "sector_scores": sector_scores
                }
            }
            return classified_data
            
        except Exception as e:
            logger.error(f"Failed to classify market regime: {e}")
            return self._default_regime(str(e))

    def _default_regime(self, error_msg: str) -> Dict[str, Any]:
        """Provides a safe default fallback regime configuration."""
        return {
            "timestamp": datetime.now().isoformat(),
            "regime": "sideways",
            "rationale": f"Fallback default activated due to classification failure: {error_msg}",
            "telemetry": {
                "nifty_close": 22000.0,
                "nifty_50ma": 22000.0,
                "nifty_200ma": 21500.0,
                "india_vix": 14.5,
                "breadth": {
                    "pct_above_50dma": 50.0,
                    "advance_decline_ratio": 1.0,
                    "advancing": 10,
                    "declining": 10
                },
                "breadth_state": "NEUTRAL",
                "smallcap_outperformance_20d": 0.0,
                "top_sector": "None",
                "sector_scores": {}
            }
        }
