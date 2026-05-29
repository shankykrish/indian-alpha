import os
import pickle
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from loguru import logger
import yfinance as yf

from indian_alpha.storage.universes import MIDCAP_100, SMALLCAP_100
from indian_alpha.storage.strategy_store import load_strategy

class HistoricalBacktestEngine:
    """
    High-performance, event-driven backtesting engine for Indian equities.
    Simulates multi-year systematic momentum breakout strategy runs with realistic execution friction.
    """
    def __init__(self, start_date: str = "2021-01-01", end_date: str = "2026-05-01"):
        self.start_date = start_date
        self.end_date = end_date
        self.universe = list(set(MIDCAP_100 + SMALLCAP_100))
        
        from indian_alpha.config import BASE_STATE_DIR
        self.cache_file = os.path.join(BASE_STATE_DIR, "backtest_universe_cache.pkl")

    def _sanitize_symbol(self, symbol: str) -> str:
        symbol = symbol.strip().upper()
        if symbol.endswith(".NS") or symbol.endswith(".BO") or symbol.startswith("^"):
            return symbol
        return f"{symbol}.NS"

    async def fetch_historical_dataset(self) -> Dict[str, pd.DataFrame]:
        """
        Downloads EOD historical data for all stocks in the universe plus Nifty benchmark.
        Caches the combined dataset locally to enable sub-second reload speeds.
        """
        if os.path.exists(self.cache_file):
            try:
                mtime = os.path.getmtime(self.cache_file)
                # Cache valid for 3 days to avoid redundant heavy downloads
                if datetime.now().timestamp() - mtime < 259200:
                    with open(self.cache_file, "rb") as f:
                        logger.info(f"Loaded backtest historical dataset from local cache: {self.cache_file}")
                        return pickle.load(f)
            except Exception as e:
                logger.error(f"Failed to load backtest data cache: {e}")

        logger.info(f"Initiating batch download for {len(self.universe)} universe stocks + NIFTY 50...")
        sanitized_symbols = [self._sanitize_symbol(s) for s in self.universe]
        
        # Download Nifty benchmark
        nifty_symbol = "^NSEI"
        all_symbols = sanitized_symbols + [nifty_symbol]
        
        def _download_all():
            return yf.download(
                all_symbols, 
                start=self.start_date, 
                end=self.end_date, 
                group_by='ticker', 
                progress=False
            )
            
        try:
            batch_df = await asyncio.to_thread(_download_all)
            
            # Reorganize into symbol -> DataFrame dictionary
            dataset = {}
            for sym in all_symbols:
                if sym in batch_df.columns.levels[0]:
                    df = batch_df[sym].dropna(subset=["Close"]).copy()
                    if not df.empty:
                        # Standardize columns to lowercase (safely handles strings and MultiIndex tuples)
                        df.columns = [c[0].lower() if isinstance(c, tuple) else str(c).lower() for c in df.columns]
                        df.index = df.index.tz_localize(None) if df.index.tz is not None else df.index
                        dataset[sym] = df
                        
            # Save to local cache
            with open(self.cache_file, "wb") as f:
                pickle.dump(dataset, f)
                
            logger.info(f"Successfully cached dataset with {len(dataset)} valid ticker histories.")
            return dataset
        except Exception as e:
            logger.error(f"Historical batch download failed: {e}")
            return {}

    def precompute_indicators(self, dataset: Dict[str, pd.DataFrame], strategy_cfg: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
        """
        Vectorizes technical indicators, relative strength scores, and composite rankings
        pre-simulation for maximum speed.
        """
        logger.info("Pre-calculating strategy indicators & relative strength ranks...")
        nifty_df = dataset.get("^NSEI")
        if nifty_df is None or nifty_df.empty:
            logger.error("Nifty index data missing. Pre-calculation aborted.")
            return {}
            
        nifty_close = nifty_df["close"]
        nifty_ret_60d = nifty_close.pct_change(60)
        nifty_ret_20d = nifty_close.pct_change(20)
        
        breakout_period = strategy_cfg.get("entry", {}).get("breakout_period", 55)
        
        processed_dataset = {}
        for symbol, df in dataset.items():
            if symbol == "^NSEI" or len(df) < 60:
                continue
                
            try:
                df = df.copy()
                close = df["close"]
                high = df["high"]
                low = df["low"]
                volume = df["volume"]
                
                # --- Moving Averages ---
                df["ma_50"] = close.rolling(50).mean()
                df["ma_200"] = close.rolling(200).mean()
                
                # --- Breakout Channels (yesterday's high lookback) ---
                df["breakout_channel"] = high.rolling(breakout_period).max().shift(1)
                
                # --- Average True Range (ATR-14) ---
                high_low = high - low
                high_close = (high - close.shift(1)).abs()
                low_close = (low - close.shift(1)).abs()
                tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                df["atr"] = tr.rolling(14).mean()
                
                # --- Relative Strength vs NIFTY (60-day & 20-day) ---
                # Re-align with Nifty dates
                stock_ret_60d = close.pct_change(60)
                stock_ret_20d = close.pct_change(20)
                
                # Align series index
                common_dates = df.index.intersection(nifty_df.index)
                if len(common_dates) < 20:
                    continue
                    
                df["rs_nifty_60d"] = (stock_ret_60d - nifty_ret_60d.loc[common_dates]) * 100.0
                df["rs_nifty_20d"] = (stock_ret_20d - nifty_ret_20d.loc[common_dates]) * 100.0
                
                # --- Composite Momentum Quality score ---
                rs_nifty_norm = ((df["rs_nifty_60d"] + 20.0) * 2.0).clip(0, 100)
                rs_sector_norm = ((df["rs_nifty_20d"] + 15.0) * 2.5).clip(0, 100)
                
                # Sharpe-like momentum persistence
                daily_ret = close.pct_change()
                mom_mean = daily_ret.rolling(20).mean()
                mom_std = daily_ret.rolling(20).std()
                mom_persistence = (mom_mean / mom_std) * np.sqrt(252)
                mom_persist_norm = ((mom_persistence + 1.0) * 35.0).fillna(0.0).clip(0, 100)
                
                # Breakout proximity relative to strategy lookback (solves ChatGPT mismatch)
                high_nd = high.rolling(breakout_period).max()
                breakout_dist = ((high_nd - close) / high_nd) * 100.0
                breakout_score = (100.0 - breakout_dist * 10.0).clip(0, 100)
                
                # Trend score
                above_50 = close > df["ma_50"]
                above_200 = close > df["ma_200"]
                trend_score = 50.0 + above_50.astype(float) * 25.0 + above_200.astype(float) * 25.0
                
                # Volume expansion
                vol_expansion = volume / volume.rolling(20).mean()
                vol_expansion_norm = (vol_expansion * 45.0).fillna(0.0).clip(0, 100)
                
                # Composite quality score (incorporating redirected theme bonus weight)
                df["composite_score"] = (
                    rs_nifty_norm * 0.25 +       # 25% Nifty relative strength
                    rs_sector_norm * 0.15 +      # 15% Sector relative strength
                    mom_persist_norm * 0.15 +    # 15% Persistence Quality
                    vol_expansion_norm * 0.20 +  # 20% Volume Expansion
                    breakout_score * 0.15 +      # 15% Breakout proximity
                    trend_score * 0.10           # 10% Trend structure
                )
                
                processed_dataset[symbol] = df
            except Exception as e:
                logger.error(f"Error pre-calculating indicators for {symbol}: {e}")
                continue
                
        return processed_dataset

    def run_backtest(self, dataset: Dict[str, pd.DataFrame], strategy_cfg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs an event-driven backtest daily simulation including dynamic risk models.
        """
        logger.info("Executing EOD event-driven daily portfolio simulation...")
        nifty_df = dataset.get("^NSEI") if "^NSEI" in dataset else yf.download("^NSEI", start=self.start_date, end=self.end_date, progress=False)
        nifty_df.columns = [c[0].lower() if isinstance(c, tuple) else str(c).lower() for c in nifty_df.columns]
        nifty_df.index = nifty_df.index.tz_localize(None) if nifty_df.index.tz is not None else nifty_df.index
        
        nifty_close = nifty_df["close"]
        nifty_ma200 = nifty_close.rolling(200).mean()
        
        # Load parameters
        risk = strategy_cfg.get("risk", {})
        entry_cfg = strategy_cfg.get("entry", {})
        market_filter = strategy_cfg.get("market_filter", {})
        
        initial_capital = 1000000.0 # 10 Lakhs INR
        cash = initial_capital
        positions = {} # symbol -> position_info
        trades_ledger = []
        equity_curve = []
        
        start_dt = pd.to_datetime(self.start_date)
        end_dt = pd.to_datetime(self.end_date)
        all_dates = nifty_df.index.sort_values()
        all_dates = all_dates[(all_dates >= start_dt) & (all_dates <= end_dt)]
        
        # dynamic parameters
        max_positions = int(risk.get("max_positions", 12))
        position_size_pct = float(risk.get("position_size_pct", 8.0)) / 100.0
        atr_stop_multiplier = float(risk.get("atr_stop_multiplier", 2.5))
        atr_trailing_multiplier = float(risk.get("atr_trailing_multiplier", 3.0))
        
        nifty_above_200ma_filter = market_filter.get("nifty_above_200dma", True)
        
        for t in all_dates:
            today_str = t.strftime("%Y-%m-%d")
            
            # --- 1. Evaluate Exits & Dynamic Trailing stops ---
            exited_symbols = []
            for symbol, pos in list(positions.items()):
                stock_df = dataset.get(symbol)
                if stock_df is None or t not in stock_df.index:
                    continue
                    
                today_bar = stock_df.loc[t]
                today_low = today_bar["low"]
                today_high = today_bar["high"]
                today_close = today_bar["close"]
                
                # Check Stop Loss / Trailing Stop trigger
                stop_price = pos["stop_price"]
                
                if today_low <= stop_price:
                    # Exit triggered!
                    qty = pos["quantity"]
                    # If open is below stop, fill at open (realistic gap down slippage!)
                    fill_price = min(stop_price, today_bar["open"])
                    
                    gross_value = qty * fill_price
                    brokerage = gross_value * 0.0015 # 0.15% execution slippage & charges (0.30% round-trip)
                    net_value = gross_value - brokerage
                    
                    cash += net_value
                    pnl = net_value - pos["capital_at_risk"]
                    pnl_pct = (fill_price - pos["entry_price"]) / pos["entry_price"] * 100.0
                    
                    trades_ledger.append({
                        "timestamp": today_str,
                        "symbol": symbol,
                        "action": "SELL",
                        "quantity": qty,
                        "price": float(fill_price),
                        "brokerage": float(brokerage),
                        "pnl": float(pnl),
                        "pnl_pct": float(pnl_pct),
                        "reason": f"ATR Exit triggered at Rs. {fill_price:.2f} (Stop level: Rs. {stop_price:.2f})"
                    })
                    
                    exited_symbols.append(symbol)
                else:
                    # Update trailing peak & stop levels
                    pos["max_price"] = max(pos["max_price"], today_high)
                    trailing_stop = pos["max_price"] - (atr_trailing_multiplier * pos["entry_atr"])
                    pos["stop_price"] = max(pos["stop_price"], trailing_stop)
                    pos["current_price"] = today_close
                    
            for sym in exited_symbols:
                del positions[sym]
                
            # --- 2. Evaluate Benchmark Trend filter ---
            nifty_ok = True
            if nifty_above_200ma_filter and t in nifty_ma200.index:
                n_close = nifty_close.loc[t]
                n_ma = nifty_ma200.loc[t]
                if pd.notna(n_close) and pd.notna(n_ma):
                    nifty_ok = n_close > n_ma
                    
            # --- 3. Evaluate Entries (Only if benchmark filter is OK and slots are free) ---
            if nifty_ok and len(positions) < max_positions:
                candidates = []
                
                for symbol, df in dataset.items():
                    if symbol in positions or symbol == "^NSEI" or t not in df.index:
                        continue
                        
                    # Find yesterday's bar to check historical breakout values
                    pos_idx = df.index.get_loc(t)
                    if pos_idx < 1:
                        continue
                    prev_t = df.index[pos_idx - 1]
                    
                    today_bar = df.loc[t]
                    prev_bar = df.loc[prev_t]
                    
                    today_close = today_bar["close"]
                    channel = prev_bar["breakout_channel"]
                    
                    # Filter for active breakout
                    if pd.notna(channel) and today_close > channel:
                        # Confirm closes above 50 & 200 DMA
                        if today_close > today_bar["ma_50"] and today_close > today_bar["ma_200"]:
                            # Confirm relative strength requirements
                            if today_bar["rs_nifty_60d"] >= float(entry_cfg.get("relative_strength_vs_nifty_min", 70)):
                                if today_bar["rs_nifty_20d"] >= float(entry_cfg.get("relative_strength_vs_sector_min", 65)):
                                    if today_bar["composite_score"] >= float(entry_cfg.get("momentum_quality_min", 75)):
                                        candidates.append({
                                            "symbol": symbol,
                                            "score": today_bar["composite_score"],
                                            "price": today_close,
                                            "atr": today_bar["atr"]
                                        })
                                        
                # Sort candidates by composite momentum score descending
                candidates.sort(key=lambda x: x["score"], reverse=True)
                
                # Execute purchases
                total_portfolio_equity = cash + sum([pos["quantity"] * pos["current_price"] for pos in positions.values()])
                capital_per_position = total_portfolio_equity * position_size_pct
                
                for cand in candidates:
                    if len(positions) >= max_positions:
                        break
                        
                    symbol = cand["symbol"]
                    price = cand["price"]
                    atr = cand["atr"]
                    
                    if cash < capital_per_position or price <= 0.0 or pd.isna(atr):
                        continue
                        
                    qty = int(capital_per_position // price)
                    if qty <= 0:
                        continue
                        
                    gross_value = qty * price
                    brokerage = gross_value * 0.0015 # 0.15% friction (0.30% round-trip)
                    total_cost = gross_value + brokerage
                    
                    if cash >= total_cost:
                        cash -= total_cost
                        initial_stop = price - (atr_stop_multiplier * atr)
                        
                        positions[symbol] = {
                            "symbol": symbol,
                            "quantity": qty,
                            "entry_price": float(price),
                            "current_price": float(price),
                            "max_price": float(price),
                            "entry_atr": float(atr),
                            "stop_price": float(initial_stop),
                            "capital_at_risk": float(total_cost)
                        }
                        
                        trades_ledger.append({
                            "timestamp": today_str,
                            "symbol": symbol,
                            "action": "BUY",
                            "quantity": qty,
                            "price": float(price),
                            "brokerage": float(brokerage),
                            "pnl": 0.0,
                            "pnl_pct": 0.0,
                            "reason": f"Momentum breakout entry. Score: {cand['score']:.1f}"
                        })
                        
            # --- 4. Log Daily Equity curves ---
            positions_val = sum([pos["quantity"] * pos["current_price"] for pos in positions.values()])
            total_equity = cash + positions_val
            equity_curve.append({
                "date": today_str,
                "portfolio_equity": float(total_equity),
                "nifty_close": float(nifty_close.loc[t]) if t in nifty_close.index else 0.0
            })
            
        # --- 5. Compile Final Backtest Summary ---
        final_equity = equity_curve[-1]["portfolio_equity"] if equity_curve else initial_capital
        total_days = (all_dates[-1] - all_dates[0]).days
        years = total_days / 365.25
        
        cagr = ((final_equity / initial_capital) ** (1 / years) - 1) * 100.0 if years > 0 else 0.0
        
        # Max Drawdown
        equities = np.array([e["portfolio_equity"] for e in equity_curve])
        peaks = np.maximum.accumulate(equities)
        drawdowns = (peaks - equities) / peaks * 100.0
        max_drawdown = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0
        
        # Win rate & metrics
        closed_trades = [t for t in trades_ledger if t["action"] == "SELL"]
        wins = [t for t in closed_trades if t["pnl"] > 0]
        losses = [t for t in closed_trades if t["pnl"] < 0]
        
        win_rate = (len(wins) / len(closed_trades) * 100.0) if closed_trades else 0.0
        
        avg_win = float(np.mean([t["pnl_pct"] for t in wins])) if wins else 0.0
        avg_loss = float(np.mean([t["pnl_pct"] for t in losses])) if losses else 0.0
        payoff_ratio = (avg_win / abs(avg_loss)) if avg_loss != 0.0 else 0.0
        
        gross_profits = sum([t["pnl"] for t in wins])
        gross_losses = sum([abs(t["pnl"]) for t in losses])
        profit_factor = (gross_profits / gross_losses) if gross_losses > 0 else 1.0
        
        return {
            "summary": {
                "start_date": self.start_date,
                "end_date": self.end_date,
                "initial_capital": initial_capital,
                "final_equity": final_equity,
                "cagr": cagr,
                "max_drawdown": max_drawdown,
                "total_trades": len(trades_ledger),
                "closed_trades": len(closed_trades),
                "win_rate": win_rate,
                "average_winner": avg_win,
                "average_loser": avg_loss,
                "payoff_ratio": payoff_ratio,
                "profit_factor": profit_factor
            },
            "trades": trades_ledger,
            "equity_curve": equity_curve
        }
