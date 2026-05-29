import os
import json
import argparse
import asyncio
from loguru import logger

from indian_alpha.research.backtester import HistoricalBacktestEngine
from indian_alpha.storage.strategy_store import load_strategy

async def main():
    parser = argparse.ArgumentParser(description="Run Indian-Alpha Historical Backtester.")
    parser.add_argument("--start", type=str, default="2021-01-01", help="Backtest start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default="2026-05-01", help="Backtest end date (YYYY-MM-DD)")
    parser.add_argument("--export", type=str, default="backtest_results.json", help="Filename to export results in state/ directory")
    args = parser.parse_args()

    logger.info("Initializing Indian-Alpha Quant Research Backtester...")
    
    # 1. Load active strategy config
    strategy_cfg = load_strategy()
    if not strategy_cfg:
        logger.error("Active strategy config not found. Aborting backtest.")
        return
        
    logger.info(f"Loaded strategy configuration version: v{strategy_cfg.get('version', '01')}")
    
    # 2. Instantiate backtesting engine
    engine = HistoricalBacktestEngine(start_date=args.start, end_date=args.end)
    
    # 3. Fetch data (loads cached file if present, else downloads)
    dataset = await engine.fetch_historical_dataset()
    if not dataset:
        logger.error("No historical data available. Aborting.")
        return
        
    # 4. Precompute strategy vectors (MA, ATR, RS, composite rankings)
    processed_dataset = engine.precompute_indicators(dataset, strategy_cfg)
    if not processed_dataset:
        logger.error("Failed to precompute technical indicators. Aborting.")
        return
        
    # 5. Run chronological simulation
    results = engine.run_backtest(processed_dataset, strategy_cfg)
    
    # 6. Save results to state directory for Streamlit dashboard pickup
    from indian_alpha.config import BASE_STATE_DIR
    os.makedirs(BASE_STATE_DIR, exist_ok=True)
    export_path = os.path.join(BASE_STATE_DIR, args.export)
    
    try:
        with open(export_path, "w") as f:
            json.dump(results, f, indent=2)
        logger.info(f"Successfully exported backtest telemetry report -> {export_path}")
    except Exception as e:
        logger.error(f"Failed to export backtest results: {e}")
        
    # 7. Render gorgeous console report
    sum_data = results["summary"]
    print("\n" + "="*60)
    print("=== INDIAN-ALPHA SYSTEMATIC MOMENTUM BACKTEST REPORT ===")
    print("="*60)
    print(f"Horizon Period   : {sum_data['start_date']} to {sum_data['end_date']}")
    print(f"Initial Capital  : Rs. {sum_data['initial_capital']:,.2f}")
    print(f"Final Account Val: Rs. {sum_data['final_equity']:,.2f}")
    print(f"CAGR (Growth Rate): {sum_data['cagr']:.2f}%")
    print(f"Max Drawdown     : -{sum_data['max_drawdown']:.2f}%")
    print(f"Profit Factor    : {sum_data['profit_factor']:.2f}x")
    print("-" * 60)
    print(f"Total Trade Logs : {sum_data['total_trades']} Trades")
    print(f"Closed Positions : {sum_data['closed_trades']} Trades")
    print(f"Closed Win Rate  : {sum_data['win_rate']:.1f}%")
    print(f"Average Winner   : +{sum_data['average_winner']:.2f}%")
    print(f"Average Loser    : {sum_data['average_loser']:.2f}%")
    print(f"Payoff Ratio     : {sum_data['payoff_ratio']:.2f} : 1")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
