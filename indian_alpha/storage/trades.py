import os
import json
from typing import List, Dict, Any
from loguru import logger
from indian_alpha.observability.metrics import global_metrics

from indian_alpha.config import TRADES_FILE

def load_trades(file_path: str = TRADES_FILE) -> List[Dict[str, Any]]:
    """Loads all simulated paper trades from the JSONL log file, ignoring comments and header lines."""
    if not os.path.exists(file_path):
        return []
        
    trades = []
    try:
        with open(file_path, "r") as f:
            for line in f:
                line_str = line.strip()
                if not line_str or line_str.startswith("#"):
                    continue
                try:
                    trade = json.loads(line_str)
                    # Filter out helper/init records if any
                    if "init" in trade:
                        continue
                    trades.append(trade)
                except json.JSONDecodeError as je:
                    logger.warning(f"Skipping malformed trade log line: {line_str}. Error: {je}")
    except Exception as e:
        logger.error(f"Error loading trade logs from {file_path}: {e}")
        
    return trades

from indian_alpha.storage.utils import clean_json_data

def save_trade(trade: Dict[str, Any], file_path: str = TRADES_FILE) -> None:
    """Appends a paper trade to the JSONL log file atomically."""
    try:
        # Create directory if missing
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Clean data to ensure JSON compliance (handles NaNs and Infs safely)
        trade = clean_json_data(trade)
        
        # Append atomically using a lock isn't strictly necessary for single worker appending,
        # but let's make sure it writes with clean line breaks.
        with open(file_path, "a") as f:
            f.write(json.dumps(trade) + "\n")
            
        global_metrics.record_db_write()
    except Exception as e:
        logger.error(f"Failed to append trade to {file_path}: {e}")
