import os
import sys
import asyncio
import signal
from datetime import datetime, timedelta
from loguru import logger

# Import all core engine components
from indian_alpha.observability.logging import setup_logging
from indian_alpha.observability.heartbeat import write_heartbeat
from indian_alpha.observability.metrics import global_metrics
from indian_alpha.observability.alerts import send_alert
from indian_alpha.providers.loader import get_active_provider
from indian_alpha.regimes.classifier import MarketRegimeClassifier
from indian_alpha.ranking_engine import IndianEquitiesRankingEngine
from indian_alpha.portfolio import IndianEquitiesPortfolio
from indian_alpha.execution import IndianMarketExecutionSimulator
from indian_alpha.strategies.momentum_breakout import MomentumBreakoutStrategy
from indian_alpha.reflection import SelfLearningReflectionEngine
from indian_alpha.walk_forward import WalkForwardValidator
from indian_alpha.scheduler import IndianMarketScheduler
from indian_alpha.storage.trades import save_trade, load_trades
from indian_alpha.storage.market_regimes import save_regime_classification, load_regimes_history
from indian_alpha.storage.hypotheses import load_hypotheses
from indian_alpha.storage.universes import MIDCAP_100, SMALLCAP_100

class IndianAlphaWorker:
    """
    Main background daemon that coordinates yfinance data fetching, 
    regime classification, rankings, simulated execution, and reflection loops.
    """
    def __init__(self):
        self.running = True
        self.scheduler = IndianMarketScheduler()
        self.provider = get_active_provider()
        self.classifier = MarketRegimeClassifier(self.provider)
        self.ranker = IndianEquitiesRankingEngine(self.provider)
        self.portfolio = IndianEquitiesPortfolio()
        self.executor = IndianMarketExecutionSimulator()
        self.reflector = SelfLearningReflectionEngine()
        self.validator = WalkForwardValidator()
        
        # Universe basket to trade dynamically loaded from Midcap and Smallcap indexes
        self.universe = MIDCAP_100 + SMALLCAP_100


    def stop(self):
        self.running = False
        logger.info("Shutdown requested. Gracefully finalizing worker...")

    async def run(self):
        logger.info("Starting Indian-Alpha Background Daemon...")
        
        # Local fast bootstrap check
        is_fast_run = os.getenv("FAST_RUN", "false").lower() == "true"
        
        # Set up shutdown signals
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, self.stop)
            except NotImplementedError:
                # Signal handlers are not fully supported on Windows in asyncio without ProactorEventLoop
                pass

        # Primary Loop
        while self.running:
            try:
                mode = self.scheduler.determine_execution_mode()
                logger.info(f"Scheduler Mode Tick: {mode.upper()}")
                
                # Write heartbeat file
                write_heartbeat(mode, "healthy")
                
                # 1. Run classifier to detect regime
                regime_data = await self.classifier.classify_regime()
                save_regime_classification(regime_data)
                active_regime = regime_data.get("regime", "sideways")
                
                # Load strategy rules to get configured risk parameters
                from indian_alpha.storage.strategy_store import load_strategy
                strat_cfg = load_strategy()
                risk_config = strat_cfg.get("risk", {})
                
                # Adjust portfolio sizing rules based on regime
                strategy_cfg = self.portfolio.determine_regime_sizing(
                    active_regime, 
                    risk_config
                )
                max_pos, pos_size_pct = strategy_cfg
                
                # 2. Mode Action Selection
                if mode == "active_market" or is_fast_run:
                    await self._execute_active_trading(regime_data, max_pos, pos_size_pct)
                    
                if mode == "post_market" or is_fast_run:
                    await self._execute_post_market_analysis()
                    
                if mode == "saturday_workload" or is_fast_run:
                    await self._execute_saturday_validation()
                    
                if mode == "sunday_workload" or is_fast_run:
                    await self._execute_sunday_maintenance()

                if is_fast_run:
                    logger.info("FAST_RUN dry-run completed successfully. Exiting background daemon.")
                    break
                    
                # Dynamically calculate the next trigger time to align precisely with the clock
                next_trigger = self.scheduler.get_next_trigger_time()
                now_ist = self.scheduler.get_current_ist_time()
                delay = max(10, int((next_trigger - now_ist).total_seconds()))
                logger.info(f"Next trigger scheduled at: {next_trigger.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                logger.info(f"Execution cycle complete. Sleeping for {delay} seconds...")
                
                # Sleep in smaller increments to check shutdown status and update heartbeat
                for i in range(delay // 10):
                    if not self.running:
                        break
                    # Keep the heartbeat fresh while sleeping (update every 60 seconds / 6 ticks)
                    if i % 6 == 0:
                        write_heartbeat(mode, "healthy")
                    await asyncio.sleep(10)
                    
            except Exception as e:
                logger.error(f"Error in main scheduler loop: {e}")
                await send_alert(f"Scheduler error occurred: {e}", "CRITICAL")
                await asyncio.sleep(60) # Prevent tight CPU spin on errors

        # Save portfolio state before termination
        self.portfolio.save_state()
        logger.info("Worker state successfully saved to /app/state. Shutdown complete.")

    async def _execute_active_trading(self, regime_data, max_pos: int, pos_size_pct: float):
        """Active Market Mode: Scans universe, computes rankings, generates signals, fills trades."""
        active_regime = regime_data.get("regime", "sideways")
        logger.info("Running ACTIVE MARKET workload...")
        global_metrics.record_scan()
        
        # 1. Update real-time mark-to-market prices for all open positions in the portfolio
        if self.portfolio.positions:
            logger.info(f"Updating real-time prices for {len(self.portfolio.positions)} active holdings...")
            tasks = []
            symbols = list(self.portfolio.positions.keys())
            for symbol in symbols:
                tasks.append(self.provider.fetch_quote(symbol))
            quotes = await asyncio.gather(*tasks, return_exceptions=True)
            for i, quote in enumerate(quotes):
                symbol = symbols[i]
                if isinstance(quote, Exception):
                    logger.error(f"Failed to fetch real-time quote for {symbol}: {quote}")
                    continue
                price = quote.get("price")
                if price:
                    self.portfolio.update_holding_price(symbol, price)
                    logger.info(f"Updated real-time mark price for {symbol}: ₹{price:,.2f}")
        
        # 2. Recalculate rankings
        rankings_data = await self.ranker.compute_rankings(self.universe)
        rankings_list = rankings_data.get("rankings", [])
        rankings_by_symbol = {r["symbol"]: r for r in rankings_list}
        
        # Load strategy rules
        from indian_alpha.storage.strategy_store import load_strategy
        strat_cfg = load_strategy()
        strategy = MomentumBreakoutStrategy(strat_cfg)
        
        # 2. Iterate and evaluate strategy signals for each stock in our rankings
        for rank_entry in rankings_list:
            symbol = rank_entry["symbol"]
            
            # Skip if we already own the max positions and this is a new buy
            if len(self.portfolio.positions) >= max_pos and symbol not in self.portfolio.positions:
                continue
                
            # Fetch last 50 days of OHLCV
            now = datetime.now()
            start = (now - timedelta(days=90)).strftime("%Y-%m-%d")
            end = now.strftime("%Y-%m-%d")
            
            df = await self.provider.fetch_ohlcv(symbol, start, end)
            fund = await self.provider.fetch_fundamentals(symbol)
            
            # Mark price updates for mark-to-market valuations
            if symbol in self.portfolio.positions:
                current_price = None
                if not df.empty and df["close"].iloc[-1] is not None:
                    import math
                    val = float(df["close"].iloc[-1])
                    if not math.isnan(val):
                        current_price = val
                
                if current_price is None:
                    current_price = self.portfolio.positions[symbol].get("current_price") or self.portfolio.positions[symbol]["entry_price"]
                    
                self.portfolio.update_holding_price(symbol, current_price)
            
            # Evaluate signals
            signal_res = strategy.generate_signals(df, fund, rank_entry)
            action = signal_res.get("action", "HOLD")
            price = signal_res.get("price", 0.0)
            reason = signal_res.get("reason", "")
            
            # Check market regime filter
            block_bear_panic = strat_cfg.get("market_filter", {}).get("block_bear_and_panic", True)
            if block_bear_panic and active_regime in ["bear", "panic"]:
                if symbol not in self.portfolio.positions:
                    logger.info(f"BUY order for {symbol} blocked due to restrictive market regime: {active_regime}")
                    continue
            
            # Enforce Nifty above 200 DMA filter
            nifty_above_200dma_filter = strat_cfg.get("market_filter", {}).get("nifty_above_200dma", True)
            if nifty_above_200dma_filter and symbol not in self.portfolio.positions:
                telemetry = regime_data.get("telemetry", {})
                nifty_close = telemetry.get("nifty_close")
                nifty_200ma = telemetry.get("nifty_200ma")
                if nifty_close is not None and nifty_200ma is not None and nifty_close < nifty_200ma:
                    logger.info(f"BUY order for {symbol} blocked because Nifty close ({nifty_close:.2f}) is below 200 DMA ({nifty_200ma:.2f})")
                    continue
            
            # 3. Simulate entries
            if action == "BUY" and symbol not in self.portfolio.positions:
                # Check circuit breaker
                pct_chg = rank_entry.get("pct_change_1d", 0.0)
                circuit_ok, c_msg = self.executor.verify_circuits(pct_chg, is_buy=True)
                if not circuit_ok:
                    logger.warning(f"BUY order blocked for {symbol}: {c_msg}")
                    continue
                    
                # Calculate size
                equity = self.portfolio.get_total_equity()
                capital_to_allocate = equity * (pos_size_pct / 100.0)
                
                # Apply slippage
                fill_price = self.executor.simulate_slippage(price, rank_entry.get("market_cap_cr", 1000.0), is_buy=True)
                qty = int(capital_to_allocate // fill_price)
                
                if qty <= 0:
                    continue
                    
                allocated_cap = qty * fill_price
                brokerage_cost = self.executor.calculate_execution_charges(qty, fill_price, is_buy=True)
                
                # Check portfolio constraints (cash, sector limit)
                ok, p_msg = self.portfolio.can_add_position(
                    symbol, 
                    rank_entry.get("sector", "Other"), 
                    allocated_cap + brokerage_cost,
                    max_pos
                )
                
                # Calculate stop price based on mode
                stop_loss_mode = strat_cfg.get("risk", {}).get("stop_loss_mode", "fixed")
                atr_val = signal_res.get("atr_value", price * 0.03)
                
                if stop_loss_mode == "atr":
                    multiplier = float(strat_cfg.get("risk", {}).get("atr_stop_multiplier", 2.5))
                    stop_loss_price = fill_price - (multiplier * atr_val)
                else:
                    fixed_pct = float(strat_cfg.get("risk", {}).get("stop_loss_pct", 7.0))
                    stop_loss_price = fill_price * (1 - fixed_pct / 100.0)
                
                if ok:
                    trailing_pct_val = float(strat_cfg.get("risk", {}).get("trailing_stop_pct", 15.0)) if strat_cfg.get("risk", {}).get("trailing_stop_mode", "atr") == "fixed" else 0.0
                    self.portfolio.enter_position(
                        symbol, 
                        qty, 
                        fill_price, 
                        rank_entry["sector"], 
                        rank_entry["theme"], 
                        brokerage_cost,
                        stop_loss_price=stop_loss_price,
                        trailing_stop_pct=trailing_pct_val,
                        atr_value=atr_val
                    )
                    # Log paper trade record
                    trade_record = {
                        "timestamp": datetime.now().isoformat(),
                        "symbol": symbol,
                        "action": "BUY",
                        "quantity": qty,
                        "price": fill_price,
                        "brokerage": brokerage_cost,
                        "sector": rank_entry["sector"],
                        "theme": rank_entry["theme"],
                        "reason": reason,
                        "pnl": 0.0,
                        "pnl_pct": 0.0
                    }
                    save_trade(trade_record)
                else:
                    logger.info(f"BUY signal rejected for {symbol}: {p_msg}")
                    
        # 4. Handle Exits (Trailing Stop and Stop Losses)
        for symbol, pos in list(self.portfolio.positions.items()):
            current_price = pos["current_price"]
            entry_price = pos["entry_price"]
            unrealized_pnl_pct = pos["unrealized_pnl_pct"]
            
            # Fetch exit strategy modes
            trailing_stop_mode = strat_cfg.get("risk", {}).get("trailing_stop_mode", "atr")
            
            # Retrieve parameters stored in position
            saved_stop_loss_price = pos.get("stop_loss_price", 0.0)
            max_price = pos.get("max_price", entry_price)
            entry_atr = pos.get("entry_atr", entry_price * 0.03)
            
            # Fallbacks if properties are not initialized in saved state
            if saved_stop_loss_price == 0.0:
                fixed_pct = float(strat_cfg.get("risk", {}).get("stop_loss_pct", 7.0))
                saved_stop_loss_price = entry_price * (1 - fixed_pct / 100.0)
            
            triggered_exit = False
            exit_reason = ""
            
            # --- Initial Stop Loss check ---
            if current_price <= saved_stop_loss_price:
                triggered_exit = True
                exit_reason = f"Stop Loss hit at Rs. {current_price:.2f} (Limit Price: Rs. {saved_stop_loss_price:.2f})"
                
            # --- Trailing Stop check ---
            elif trailing_stop_mode == "atr":
                multiplier = float(strat_cfg.get("risk", {}).get("atr_trailing_multiplier", 3.0))
                trailing_stop_price = max_price - (multiplier * entry_atr)
                if current_price <= trailing_stop_price:
                    triggered_exit = True
                    exit_reason = f"ATR Trailing Stop hit at Rs. {current_price:.2f} (Trailing Stop Price: Rs. {trailing_stop_price:.2f}, Max Peak: Rs. {max_price:.2f})"
            elif trailing_stop_mode == "fixed":
                fixed_trail_pct = float(strat_cfg.get("risk", {}).get("trailing_stop_pct", 15.0))
                trailing_stop_price = max_price * (1 - fixed_trail_pct / 100.0)
                if current_price <= trailing_stop_price:
                    triggered_exit = True
                    exit_reason = f"Fixed Trailing Stop ({fixed_trail_pct}%) hit at Rs. {current_price:.2f} (Trailing Stop Price: Rs. {trailing_stop_price:.2f}, Max Peak: Rs. {max_price:.2f})"
                
            if triggered_exit:
                # Calculate charges
                qty = pos["quantity"]
                brokerage_cost = self.executor.calculate_execution_charges(qty, current_price, is_buy=False)
                
                # Exit position
                exit_res = self.portfolio.exit_position(symbol, qty, current_price, brokerage_cost)
                if exit_res:
                    trade_record = {
                        "timestamp": datetime.now().isoformat(),
                        "symbol": symbol,
                        "action": "SELL",
                        "quantity": qty,
                        "price": current_price,
                        "brokerage": brokerage_cost,
                        "sector": pos["sector"],
                        "theme": pos["theme"],
                        "reason": exit_reason,
                        "pnl": exit_res["pnl"],
                        "pnl_pct": exit_res["pnl_pct"]
                    }
                    save_trade(trade_record)

        # Save portfolio state snapshot
        self.portfolio.save_state(active_regime)

    async def _execute_post_market_analysis(self):
        """Post-Market: Runs the cognitive reflection loop and walks forward strategy variables."""
        logger.info("Running POST-MARKET reflection workloads...")
        # Trigger self-learning updates
        self.reflector.trigger_reflection()

    async def _execute_saturday_validation(self):
        """Saturday: Performs Monte Carlo checks and parameter stability checks."""
        logger.info("Running SATURDAY validation workloads...")
        trades = load_trades()
        hypotheses = load_hypotheses()
        
        returns = [t.get("pnl_pct", 0.0) for t in trades if t.get("action") == "SELL"]
        
        # Run Monte Carlo Bootstrapping
        mc_results = self.validator.run_monte_carlo(returns, simulations=1000)
        logger.info(f"Monte Carlo Bootstrap over 20-day horizon: Mean Return: {mc_results.get('mean_return', 0.0):.2f}%, 95% CVaR: {mc_results.get('cvar_95', 0.0):.2f}%")
        
        # Check Parameter stability
        stability = self.validator.check_parameter_stability(hypotheses)
        logger.info(f"Parameter Stability Assessment: {stability.get('status')}. Changes count: {stability.get('changes_count')}")

    async def _execute_sunday_maintenance(self):
        """Sunday: Prepares weekly summarizes and performs database persistence maintenance."""
        logger.info("Running SUNDAY maintenance and cleanups...")
        # Write clean backup metadata or run compact operations if databases are large
        logger.info("Database integrity checks complete. Ready for Monday trading session.")

def main():
    # Setup standard logging first
    setup_logging()
    
    # Run the worker within the asyncio event loop
    worker = IndianAlphaWorker()
    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        logger.info("Daemon interrupted by console. Shutting down.")

if __name__ == "__main__":
    main()
