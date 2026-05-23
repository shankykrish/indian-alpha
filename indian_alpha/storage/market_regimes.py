import os
import json
from typing import List, Dict, Any
from datetime import datetime
from loguru import logger
from indian_alpha.observability.metrics import global_metrics

from indian_alpha.config import REGIMES_FILE

def load_regimes_history(file_path: str = REGIMES_FILE) -> List[Dict[str, Any]]:
    """Loads historical classified market regimes."""
    if not os.path.exists(file_path):
        return []
        
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading regime history from {file_path}: {e}")
        return []

from indian_alpha.storage.utils import clean_json_data

def save_regime_classification(
    regime_info: Dict[str, Any], 
    file_path: str = REGIMES_FILE
) -> None:
    """Appends the newly classified market regime to history atomically."""
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        history = load_regimes_history(file_path)
        
        # Add timestamp if not present
        if "timestamp" not in regime_info:
            regime_info["timestamp"] = datetime.now().isoformat()
            
        history.append(regime_info)
        
        # Keep history bounded if it grows too large, e.g. last 1000 classifications
        if len(history) > 1000:
            history = history[-1000:]
            
        # Clean data to ensure JSON compliance (handles NaNs and Infs safely)
        history = clean_json_data(history)
        
        temp_path = f"{file_path}.tmp"
        with open(temp_path, "w") as f:
            json.dump(history, f, indent=2)
        os.replace(temp_path, file_path)
        
        global_metrics.record_db_write()
        logger.info(f"Market regime recorded: {regime_info.get('regime')}")
    except Exception as e:
        logger.error(f"Failed to save market regime classification: {e}")
