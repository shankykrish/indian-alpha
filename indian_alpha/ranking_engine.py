import asyncio
import pandas as pd
import numpy as np
import yfinance as yf
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta
from loguru import logger

from indian_alpha.providers.base import MarketDataProvider
from indian_alpha.storage.rankings import save_rankings
from indian_alpha.storage.universes import MIDCAP_100, SMALLCAP_100

class IndianEquitiesRankingEngine:
    """
    Computes a composite, multi-factor momentum score (0 to 100) for Indian equities.
    Tailored specifically to identify PSU momentum, defense, capital goods, and smallcap breakouts.
    """
    def __init__(self, provider: MarketDataProvider):
        self.provider = provider

    async def compute_rankings(self, symbols: List[str] = None) -> Dict[str, Any]:
        """
        Re-engineered two-phase index screener.
        Phase 1: High-speed batch screener over 200 stocks.
        Phase 2: Targeted deep fetch and scoring for the Top 15 Midcaps + Top 15 Smallcaps.
        """
        # If no symbols list provided, combine our default mid/small cap universes
        if not symbols:
            symbols = MIDCAP_100 + SMALLCAP_100
            
        logger.info(f"Starting Dynamic Multi-Cap Screener for {len(symbols)} candidates...")
        now = datetime.now()
        start_date = (now - timedelta(days=150)).strftime("%Y-%m-%d")
        end_date = now.strftime("%Y-%m-%d")

        # 1. Fetch benchmark index NIFTY 50
        nifty_df = await self.provider.fetch_index_data("NIFTY50", start_date, end_date)
        if nifty_df.empty:
            logger.error("Failed to load Nifty 50 benchmark data for ranking. Aborting.")
            return {"last_updated": None, "rankings": []}
            
        nifty_close_col = "close" if "close" in nifty_df.columns else nifty_df.columns[0]
        nifty_df.index = nifty_df.index.tz_localize(None) if nifty_df.index.tz is not None else nifty_df.index
        nifty_closes = nifty_df[nifty_close_col]
        
        # 2. Fetch sector data to know sector performance
        sector_dfs = await self.provider.fetch_sector_data()

        # =====================================================================
        # PHASE 1: Batch Download Price Data for High-Speed Screener
        # =====================================================================
        logger.info(f"PHASE 1: Running batch price download for {len(symbols)} stocks...")
        
        def _batch_download():
            return yf.download(symbols, start=start_date, end=end_date, group_by='ticker', progress=False)
            
        try:
            batch_df = await asyncio.to_thread(_batch_download)
        except Exception as e:
            logger.error(f"Failed to download batch data: {e}")
            return {"last_updated": None, "rankings": []}

        # 3. High-Speed Screening in Memory
        logger.info("PHASE 1: Scoring and filtering constituents...")
        midcap_candidates = []
        smallcap_candidates = []
        
        for symbol in symbols:
            try:
                # Check if symbol exists in batch download levels
                if symbol not in batch_df.columns.levels[0]:
                    continue
                df = batch_df[symbol].dropna().copy()
                df.index = df.index.tz_localize(None) if df.index.tz is not None else df.index
                if len(df) < 20:
                    continue
                
                close = df["Close"]
                high = df["High"]
                
                # relative strength vs nifty 50 (60-day)
                common_dates = df.index.intersection(nifty_df.index)
                if len(common_dates) < 20:
                    continue
                stock_common_close = close.loc[common_dates]
                nifty_common_close = nifty_closes.loc[common_dates]
                
                stock_ret_60d = ((stock_common_close.iloc[-1] - stock_common_close.iloc[-60]) / stock_common_close.iloc[-60]) if len(stock_common_close) >= 60 else 0.0
                nifty_ret_60d = ((nifty_common_close.iloc[-1] - nifty_common_close.iloc[-60]) / nifty_common_close.iloc[-60]) if len(nifty_common_close) >= 60 else 0.0
                rs_vs_nifty = (stock_ret_60d - nifty_ret_60d) * 100.0
                
                # momentum persistence
                ret_series = close.pct_change().dropna()
                mom_mean = ret_series.rolling(20).mean().iloc[-1] if len(ret_series) >= 20 else 0.0
                mom_std = ret_series.rolling(20).std().iloc[-1] if len(ret_series) >= 20 else 0.0
                mom_persistence = (mom_mean / mom_std) * np.sqrt(252) if mom_std > 0 else 0.0
                if np.isnan(mom_persistence) or np.isinf(mom_persistence):
                    mom_persistence = 0.0
                    
                # breakout distance
                high_20d = high.rolling(20).max().iloc[-1] if len(high) >= 20 else high.iloc[-1]
                breakout_dist = ((high_20d - close.iloc[-1]) / high_20d) * 100.0
                breakout_score = max(0.0, 100.0 - breakout_dist * 10.0)
                
                # Trend consistency
                ma_50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else close.iloc[-1]
                ma_200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else close.iloc[-1]
                above_50 = (close.iloc[-1] > ma_50)
                above_200 = (close.iloc[-1] > ma_200)
                trend_score = 50.0 + (25.0 if above_50 else -25.0) + (25.0 if above_200 else -25.0)
                
                # Compute preliminary screener score
                rs_nifty_norm = min(100.0, max(0.0, (rs_vs_nifty + 20.0) * 2.0))
                mom_persist_norm = min(100.0, max(0.0, (mom_persistence + 1.0) * 35.0))
                
                prelim_score = (
                    rs_nifty_norm * 0.40 +
                    mom_persist_norm * 0.30 +
                    breakout_score * 0.20 +
                    trend_score * 0.10
                )
                
                record = {
                    "symbol": symbol,
                    "prelim_score": prelim_score
                }
                
                # Classify based on universe category
                if symbol in MIDCAP_100:
                    midcap_candidates.append(record)
                elif symbol in SMALLCAP_100:
                    smallcap_candidates.append(record)
                else:
                    midcap_candidates.append(record)
                    
            except Exception as e:
                continue

        # Sort and select Top 15 of each category
        midcap_candidates.sort(key=lambda x: x["prelim_score"], reverse=True)
        smallcap_candidates.sort(key=lambda x: x["prelim_score"], reverse=True)
        
        top_midcaps = [x["symbol"] for x in midcap_candidates[:15]]
        top_smallcaps = [x["symbol"] for x in smallcap_candidates[:15]]
        selected_leaders = top_midcaps + top_smallcaps
        
        logger.info(f"PHASE 1 COMPLETE: Isolated {len(top_midcaps)} Midcap leaders and {len(top_smallcaps)} Smallcap leaders.")

        # =====================================================================
        # PHASE 2: Targeted Deep Fetch for Filtered Leaders (30 Tickers)
        # =====================================================================
        logger.info(f"PHASE 2: Fetching deep fundamentals & OHLCV for top {len(selected_leaders)} leaders...")
        
        all_ohlcv: Dict[str, pd.DataFrame] = {}
        all_fundamentals: Dict[str, Dict[str, Any]] = {}
        
        for symbol in selected_leaders:
            df = await self.provider.fetch_ohlcv(symbol, start_date, end_date)
            fund = await self.provider.fetch_fundamentals(symbol)
            if not df.empty and len(df) >= 20:
                df.index = df.index.tz_localize(None) if df.index.tz is not None else df.index
                all_ohlcv[symbol] = df
                all_fundamentals[symbol] = fund
            await asyncio.sleep(0.4)  # Safety delay (Phase 2 only has 30 symbols, so very safe and fast)

        # 4. Compute full composite momentum scores for top leaders
        scored_universe: List[Dict[str, Any]] = []
        
        for symbol, df in all_ohlcv.items():
            try:
                fund = all_fundamentals.get(symbol, {})
                close = df["close"]
                volume = df["volume"]
                
                # --- FACTOR 1: Relative Strength vs NIFTY 50 (20%) ---
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
                    sector_df.index = sector_df.index.tz_localize(None) if sector_df.index.tz is not None else sector_df.index
                    sector_close = sector_df["close" if "close" in sector_df.columns else sector_df.columns[0]]
                    sec_dates = df.index.intersection(sector_df.index)
                    if len(sec_dates) >= 20:
                        stock_ret_20d = ((close.loc[sec_dates].iloc[-1] - close.loc[sec_dates].iloc[-20]) / close.loc[sec_dates].iloc[-20])
                        sec_ret_20d = ((sector_close.loc[sec_dates].iloc[-1] - sector_close.loc[sec_dates].iloc[-20]) / sector_close.loc[sec_dates].iloc[-20])
                        rs_vs_sector = (stock_ret_20d - sec_ret_20d) * 100.0
                else:
                    rs_vs_sector = rs_vs_nifty * 0.7
                    
                # --- FACTOR 3: Momentum Persistence (15%) ---
                ret_series = close.pct_change().dropna()
                mom_mean = ret_series.rolling(20).mean().iloc[-1]
                mom_std = ret_series.rolling(20).std().iloc[-1]
                mom_persistence = (mom_mean / mom_std) * np.sqrt(252) if mom_std > 0 else 0.0
                if np.isnan(mom_persistence) or np.isinf(mom_persistence):
                    mom_persistence = 0.0
                    
                # --- FACTOR 4: Delivery Volume Expansion (15%) ---
                del_col = "delivery_volume" if "delivery_volume" in df.columns else "volume"
                recent_del = df[del_col].iloc[-5:].mean()
                historical_del = df[del_col].iloc[-20:].mean()
                delivery_expansion = (recent_del / historical_del) if historical_del > 0 else 1.0
                
                # --- FACTOR 5: Breakout Quality (10%) ---
                high_20d = df["high"].rolling(20).max().iloc[-1]
                breakout_dist = ((high_20d - close.iloc[-1]) / high_20d) * 100.0
                breakout_score = max(0.0, 100.0 - breakout_dist * 10.0)
                
                # --- FACTOR 6: Trend Consistency (10%) ---
                ma_50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else close.iloc[-1]
                ma_200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else close.iloc[-1]
                above_50 = (close.iloc[-1] > ma_50)
                above_200 = (close.iloc[-1] > ma_200)
                trend_score = 50.0 + (25.0 if above_50 else -25.0) + (25.0 if above_200 else -25.0)
                
                # --- FACTOR 7: Liquidity Quality (5%) ---
                avg_vol_20d = volume.iloc[-20:].mean()
                liquidity_score = min(100.0, (avg_vol_20d / 5000000.0) * 100.0)
                
                # --- FACTOR 8: Sector/Theme Leadership (10%) ---
                theme = fund.get("theme", "General")
                theme_bonus = 0.0
                if theme in ["PSU", "Defense", "Railway", "Capital Goods"]:
                    theme_bonus = 20.0

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
                
                composite_score = min(100.0, max(0.0, composite_score))
                
                universe_type = "Midcap" if symbol in MIDCAP_100 else "Smallcap"
                
                scored_universe.append({
                    "symbol": symbol,
                    "name": fund.get("long_name", symbol),
                    "sector": fund.get("sector", "Unknown"),
                    "theme": theme,
                    "universe_type": universe_type,
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
                logger.error(f"Error scoring {symbol} in Phase 2: {e}")

        # Sort universe by composite score descending
        scored_universe.sort(key=lambda x: x["composite_score"], reverse=True)
        
        logger.info("Computed Rankings completed. Top 5 Momentum Candidates:")
        for idx, entry in enumerate(scored_universe[:5]):
            logger.info(f"{idx+1}. {entry['symbol']} - Score: {entry['composite_score']:.2f} (Theme: {entry['theme']})")

        rankings_data = {
            "last_updated": datetime.now().isoformat(),
            "rankings": scored_universe
        }
        
        save_rankings(rankings_data)
        return rankings_data

