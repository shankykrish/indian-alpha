import asyncio
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta
from loguru import logger

from indian_alpha.providers.base import MarketDataProvider
from indian_alpha.storage.rankings import save_rankings

class IndianEquitiesRankingEngine:
    """
    Computes a composite, multi-factor momentum score (0 to 100) for Indian equities.
    Tailored specifically to identify PSU momentum, defense, capital goods, and smallcap breakouts.
    """
    def __init__(self, provider: MarketDataProvider):
        self.provider = provider

    async def compute_rankings(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Runs full rankings analysis for a list of equity symbols.
        Fetches data in parallel, applies the factor models, and stores rankings.
        """
        logger.info(f"Starting composite ranking engine for {len(symbols)} symbols...")
        now = datetime.now()
        start_date = (now - timedelta(days=150)).strftime("%Y-%m-%d")
        end_date = now.strftime("%Y-%m-%d")

        # 1. Fetch benchmark index NIFTY 50
        nifty_df = await self.provider.fetch_index_data("NIFTY50", start_date, end_date)
        if nifty_df.empty:
            logger.error("Failed to load Nifty 50 benchmark data for ranking. Aborting.")
            return {"last_updated": None, "rankings": []}
            
        nifty_close_col = "close" if "close" in nifty_df.columns else nifty_df.columns[0]
        nifty_closes = nifty_df[nifty_close_col]
        
        # 2. Fetch sector data to know sector performance
        sector_dfs = await self.provider.fetch_sector_data()
        
        # 3. Fetch OHLCV + Fundamentals for all stocks in parallel
        # Batch to prevent overloading the yfinance provider
        batch_size = 15
        all_ohlcv: Dict[str, pd.DataFrame] = {}
        all_fundamentals: Dict[str, Dict[str, Any]] = {}
        
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i+batch_size]
            tasks_ohlcv = [self.provider.fetch_ohlcv(s, start_date, end_date) for s in batch]
            tasks_fund = [self.provider.fetch_fundamentals(s) for s in batch]
            
            results_ohlcv = await asyncio.gather(*tasks_ohlcv)
            results_fund = await asyncio.gather(*tasks_fund)
            
            for s, df, fund in zip(batch, results_ohlcv, results_fund):
                if not df.empty and len(df) >= 20:
                    all_ohlcv[s] = df
                    all_fundamentals[s] = fund
                    
            await asyncio.sleep(0.5) # Gentle pause

        logger.info(f"Loaded valid OHLCV and fundamental records for {len(all_ohlcv)} stocks.")

        # 4. Compute momentum factors
        scored_universe: List[Dict[str, Any]] = []
        
        for symbol, df in all_ohlcv.items():
            try:
                fund = all_fundamentals.get(symbol, {})
                close = df["close"]
                volume = df["volume"]
                
                # --- FACTOR 1: Relative Strength vs NIFTY 50 (20%) ---
                # Align dates with nifty
                common_dates = df.index.intersection(nifty_df.index)
                if len(common_dates) < 20:
                    continue
                stock_common_close = close.loc[common_dates]
                nifty_common_close = nifty_closes.loc[common_dates]
                
                stock_ret_60d = ((stock_common_close.iloc[-1] - stock_common_close.iloc[-60]) / stock_common_close.iloc[-60]) if len(stock_common_close) >= 60 else 0.0
                nifty_ret_60d = ((nifty_common_close.iloc[-1] - nifty_common_close.iloc[-60]) / nifty_common_close.iloc[-60]) if len(nifty_common_close) >= 60 else 0.0
                rs_vs_nifty = (stock_ret_60d - nifty_ret_60d) * 100.0
                
                # --- FACTOR 2: Relative Strength vs Sector (15%) ---
                sector_name = fund.get("sector")
                rs_vs_sector = 0.0
                sector_df = sector_dfs.get(f"NIFTY_{sector_name.upper().replace(' ', '_')}" if sector_name else "")
                if sector_df is not None and not sector_df.empty:
                    sector_close = sector_df["close" if "close" in sector_df.columns else sector_df.columns[0]]
                    sec_dates = df.index.intersection(sector_df.index)
                    if len(sec_dates) >= 20:
                        stock_ret_20d = ((close.loc[sec_dates].iloc[-1] - close.loc[sec_dates].iloc[-20]) / close.loc[sec_dates].iloc[-20])
                        sec_ret_20d = ((sector_close.loc[sec_dates].iloc[-1] - sector_close.loc[sec_dates].iloc[-20]) / sector_close.loc[sec_dates].iloc[-20])
                        rs_vs_sector = (stock_ret_20d - sec_ret_20d) * 100.0
                else:
                    # fallback
                    rs_vs_sector = rs_vs_nifty * 0.7
                    
                # --- FACTOR 3: Momentum Persistence (15%) ---
                # Sharpe-like momentum: average 20-day return divided by standard deviation of returns
                ret_series = close.pct_change().dropna()
                mom_mean = ret_series.rolling(20).mean().iloc[-1]
                mom_std = ret_series.rolling(20).std().iloc[-1]
                mom_persistence = (mom_mean / mom_std) * np.sqrt(252) if mom_std > 0 else 0.0
                if np.isnan(mom_persistence) or np.isinf(mom_persistence):
                    mom_persistence = 0.0
                    
                # --- FACTOR 4: Delivery Volume Expansion (15%) ---
                # Check recent 5-day average delivery volume compared to 20-day average
                del_col = "delivery_volume" if "delivery_volume" in df.columns else "volume"
                recent_del = df[del_col].iloc[-5:].mean()
                historical_del = df[del_col].iloc[-20:].mean()
                delivery_expansion = (recent_del / historical_del) if historical_del > 0 else 1.0
                
                # --- FACTOR 5: Breakout Quality (10%) ---
                # Distance from 20-day high. 0% means sitting exactly on a breakout
                high_20d = df["high"].rolling(20).max().iloc[-1]
                breakout_dist = ((high_20d - close.iloc[-1]) / high_20d) * 100.0
                # Higher score if closer to or exceeding high (negative breakout dist is great!)
                breakout_score = max(0.0, 100.0 - breakout_dist * 10.0)
                
                # --- FACTOR 6: Trend Consistency (10%) ---
                # Proximity of current close above 50 DMA and 200 DMA
                ma_50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else close.iloc[-1]
                ma_200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else close.iloc[-1]
                above_50 = (close.iloc[-1] > ma_50)
                above_200 = (close.iloc[-1] > ma_200)
                trend_score = 50.0 + (25.0 if above_50 else -25.0) + (25.0 if above_200 else -25.0)
                
                # --- FACTOR 7: Liquidity Quality (5%) ---
                # Average daily volume traded (higher is better for slippage)
                avg_vol_20d = volume.iloc[-20:].mean()
                liquidity_score = min(100.0, (avg_vol_20d / 5000000.0) * 100.0)  # capped at 5M shares per day
                
                # --- FACTOR 8: Sector/Theme Leadership (10%) ---
                # Special momentum premium if sector is high momentum (e.g. PSU, Defense, Railway)
                theme = fund.get("theme", "General")
                theme_bonus = 0.0
                if theme in ["PSU", "Defense", "Railway", "Capital Goods"]:
                    theme_bonus = 20.0  # Big structural theme premium

                # Normalize and map factors to 0-100 range
                rs_nifty_norm = min(100.0, max(0.0, (rs_vs_nifty + 20.0) * 2.0))
                rs_sector_norm = min(100.0, max(0.0, (rs_vs_sector + 15.0) * 2.5))
                mom_persist_norm = min(100.0, max(0.0, (mom_persistence + 1.0) * 35.0))
                del_expansion_norm = min(100.0, max(0.0, (delivery_expansion) * 45.0))
                
                # Calculate composite score
                composite_score = (
                    rs_nifty_norm * 0.20 +
                    rs_sector_norm * 0.15 +
                    mom_persist_norm * 0.15 +
                    del_expansion_norm * 0.15 +
                    breakout_score * 0.10 +
                    trend_score * 0.10 +
                    liquidity_score * 0.05 +
                    min(100.0, theme_bonus * 5.0) * 0.10
                )
                
                # Cap composite at 100
                composite_score = min(100.0, max(0.0, composite_score))
                
                scored_universe.append({
                    "symbol": symbol,
                    "name": fund.get("long_name", symbol),
                    "sector": fund.get("sector", "Unknown"),
                    "theme": theme,
                    "market_cap_cr": float(fund.get("market_cap", 0.0) / 10000000.0),
                    "pe_ratio": float(fund.get("pe_ratio", 0.0)),
                    "close": float(close.iloc[-1]),
                    "pct_change_1d": float(((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2]) * 100.0),
                    "factors": {
                        "rs_vs_nifty": float(rs_vs_nifty),
                        "rs_vs_sector": float(rs_vs_sector),
                        "momentum_persistence": float(mom_persistence),
                        "delivery_expansion": float(delivery_expansion),
                        "breakout_proximity_pct": float(breakout_dist)
                    },
                    "composite_score": float(composite_score)
                })
            except Exception as e:
                logger.error(f"Error scoring {symbol}: {e}")

        # Sort universe by composite score descending
        scored_universe.sort(key=lambda x: x["composite_score"], reverse=True)
        
        # Log top 5
        logger.info("Computed Rankings completed. Top 5 Momentum Candidates:")
        for idx, entry in enumerate(scored_universe[:5]):
            logger.info(f"{idx+1}. {entry['symbol']} - Score: {entry['composite_score']:.2f} (Theme: {entry['theme']})")

        rankings_data = {
            "last_updated": datetime.now().isoformat(),
            "rankings": scored_universe
        }
        
        save_rankings(rankings_data)
        return rankings_data
