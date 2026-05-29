import os
import copy
import asyncio
from loguru import logger
import warnings

# Disable pandas warnings
warnings.filterwarnings('ignore')

from indian_alpha.research.backtester import HistoricalBacktestEngine
from indian_alpha.storage.strategy_store import load_strategy

def format_grid(headers, rows):
    # Custom lightweight grid formatter
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(val)))
            
    border = "+" + "+".join(["-" * (w + 2) for w in col_widths]) + "+"
    
    output = []
    output.append(border)
    output.append("|" + "|".join([f" {h:<{col_widths[i]}} " for i, h in enumerate(headers)]) + "|")
    output.append(border)
    for row in rows:
        output.append("|" + "|".join([f" {str(val):<{col_widths[i]}} " for i, val in enumerate(row)]) + "|")
    output.append(border)
    return "\n".join(output)

async def run_stability_sweep(dataset, base_cfg):
    print("\n" + "="*80)
    print("=== TEST 1: PARAMETER STABILITY SWEEP (2021-01-01 to 2026-05-01) ===")
    print("="*80)
    print("Running stability checks over various Breakout Channels and ATR Stops to check for robust parameter plateaus...\n")
    
    breakout_periods = [50, 55, 60]
    atr_stops = [2.0, 2.5, 3.0]
    
    results_table = []
    
    for bp in breakout_periods:
        for atr in atr_stops:
            # Deep copy configuration to isolate adjustments
            cfg = copy.deepcopy(base_cfg)
            cfg["entry"]["breakout_period"] = bp
            cfg["risk"]["atr_stop_multiplier"] = atr
            
            # Re-instantiate engine for full period
            engine = HistoricalBacktestEngine(start_date="2021-01-01", end_date="2026-05-01")
            
            # Precompute indicators under the new breakout period parameter
            processed = engine.precompute_indicators(dataset, cfg)
            
            # Run event-driven simulation
            res = engine.run_backtest(processed, cfg)
            
            sum_data = res["summary"]
            results_table.append([
                f"{bp} Days",
                f"{atr}x ATR",
                f"{sum_data['cagr']:.2f}%",
                f"-{sum_data['max_drawdown']:.2f}%",
                f"{sum_data['profit_factor']:.2f}x",
                f"{sum_data['total_trades']} Trades",
                f"{sum_data['win_rate']:.1f}%",
                f"{sum_data['payoff_ratio']:.2f} : 1"
            ])
            print(f"Completed Sweep: Breakout={bp}d, Stop={atr}x ATR | CAGR={sum_data['cagr']:.2f}%, MDD=-{sum_data['max_drawdown']:.2f}%")
            
    print("\n" + "="*80)
    print("=== PARAMETER STABILITY SWEEP RESULTS SUMMARY ===")
    print("="*80)
    headers = ["Breakout", "ATR Stop", "CAGR", "Max DD", "Profit Factor", "Total Trades", "Win Rate", "Payoff Ratio"]
    print(format_grid(headers, results_table))
    print("="*80 + "\n")

async def run_walk_forward(dataset, base_cfg):
    print("\n" + "="*80)
    print("=== TEST 2: OUT-OF-SAMPLE WALK-FORWARD VALIDATION ===")
    print("="*80)
    print("Splitting the dataset into In-Sample (IS) Training and Out-of-Sample (OOS) Testing periods:")
    print("- In-Sample (IS)  : 2021-01-01 to 2023-12-31 (~3 years)")
    print("- Out-of-Sample (OOS) : 2024-01-01 to 2026-05-01 (~2.4 years)\n")
    
    # 1. Run In-Sample
    logger.info("Executing In-Sample (IS) simulation [2021-2023]...")
    is_engine = HistoricalBacktestEngine(start_date="2021-01-01", end_date="2023-12-31")
    is_processed = is_engine.precompute_indicators(dataset, base_cfg)
    is_res = is_engine.run_backtest(is_processed, base_cfg)
    is_sum = is_res["summary"]
    
    # 2. Run Out-of-Sample
    logger.info("Executing Out-of-Sample (OOS) simulation [2024-2026]...")
    oos_engine = HistoricalBacktestEngine(start_date="2024-01-01", end_date="2026-05-01")
    oos_processed = oos_engine.precompute_indicators(dataset, base_cfg)
    oos_res = oos_engine.run_backtest(oos_processed, base_cfg)
    oos_sum = oos_res["summary"]
    
    # Render Comparison Table
    comparison_table = [
        ["Start Date", "2021-01-01", "2024-01-01"],
        ["End Date", "2023-12-31", "2026-05-01"],
        ["Years Horizon", "3.0 Years", "2.33 Years"],
        ["Initial Capital", "Rs. 1,000,000.00", "Rs. 1,000,000.00"],
        ["Final Account Val", f"Rs. {is_sum['final_equity']:,.2f}", f"Rs. {oos_sum['final_equity']:,.2f}"],
        ["CAGR", f"{is_sum['cagr']:.2f}%", f"{oos_sum['cagr']:.2f}%"],
        ["Max Drawdown", f"-{is_sum['max_drawdown']:.2f}%", f"-{oos_sum['max_drawdown']:.2f}%"],
        ["Profit Factor", f"{is_sum['profit_factor']:.2f}x", f"{oos_sum['profit_factor']:.2f}x"],
        ["Total Trades", f"{is_sum['total_trades']}", f"{oos_sum['total_trades']}"],
        ["Win Rate", f"{is_sum['win_rate']:.1f}%", f"{oos_sum['win_rate']:.1f}%"],
        ["Payoff Ratio", f"{is_sum['payoff_ratio']:.2f} : 1", f"{oos_sum['payoff_ratio']:.2f} : 1"]
    ]
    
    print("\n" + "="*80)
    print("=== WALK-FORWARD VALIDATION SUMMARY REPORT ===")
    print("="*80)
    headers = ["Metric", "In-Sample Training (2021-2023)", "Out-of-Sample Testing (2024-2026)"]
    print(format_grid(headers, comparison_table))
    print("="*80 + "\n")

async def main():
    logger.remove()  # Mute general loguru noise during sweep
    
    # 1. Load active strategy config
    strategy_cfg = load_strategy()
    if not strategy_cfg:
        print("Active strategy config not found. Aborting.")
        return
        
    # 2. Instantiate base engine to load cached historical dataset
    # We load the full range so it's loaded in memory once for speed
    base_engine = HistoricalBacktestEngine(start_date="2021-01-01", end_date="2026-05-01")
    dataset = await base_engine.fetch_historical_dataset()
    if not dataset:
        print("Dataset missing. Aborting.")
        return
        
    # Run the robustness sweeps
    await run_stability_sweep(dataset, strategy_cfg)
    await run_walk_forward(dataset, strategy_cfg)

if __name__ == "__main__":
    asyncio.run(main())
