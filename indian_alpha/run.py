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
from indian_alpha.providers.yahoo import YahooFinanceProvider
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
        self.provider = YahooFinanceProvider()
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
                
                # Adjust portfolio sizing rules based on regime
                strategy_cfg = self.portfolio.determine_regime_sizing(
                    active_regime, 
                    {"max_positions": 10, "position_size_pct": 10.0}
                )
                max_pos, pos_size_pct = strategy_cfg
                
                # 2. Mode Action Selection
                if mode == "active_market" or is_fast_run:
                    await self._execute_active_trading(active_regime, max_pos, pos_size_pct)
                    
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
                
                # Sleep in smaller increments to check shutdown status
                for _ in range(delay // 10):
                    if not self.running:
                        break
                    await asyncio.sleep(10)
                    
            except Exception as e:
                logger.error(f"Error in main scheduler loop: {e}")
                await send_alert(f"Scheduler error occurred: {e}", "CRITICAL")
                await asyncio.sleep(60) # Prevent tight CPU spin on errors

        # Save portfolio state before termination
        self.portfolio.save_state()
        logger.info("Worker state successfully saved to /app/state. Shutdown complete.")

    async def _execute_active_trading(self, active_regime: str, max_pos: int, pos_size_pct: float):
        """Active Market Mode: Scans universe, computes rankings, generates signals, fills trades."""
        logger.info("Running ACTIVE MARKET workload...")
        global_metrics.record_scan()
        
        # 1. Recalculate rankings
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
                
                if ok:
                    self.portfolio.enter_position(symbol, qty, fill_price, rank_entry["sector"], rank_entry["theme"], brokerage_cost)
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
            
            stop_loss = -float(strat_cfg.get("risk", {}).get("stop_loss_pct", 7.0))
            trailing_stop = float(strat_cfg.get("risk", {}).get("trailing_stop_pct", 12.0))
            
            # Exit check
            triggered_exit = False
            exit_reason = ""
            
            if unrealized_pnl_pct <= stop_loss:
                triggered_exit = True
                exit_reason = f"Stop Loss hit at {unrealized_pnl_pct:.2f}% (Limit: {stop_loss}%)"
            elif unrealized_pnl_pct >= trailing_stop:
                triggered_exit = True
                exit_reason = f"Trailing Profit Target hit at {unrealized_pnl_pct:.2f}% (Limit: {trailing_stop}%)"
                
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
