import os
import json
from typing import List, Dict, Any
from datetime import datetime
from loguru import logger
from indian_alpha.observability.metrics import global_metrics

from indian_alpha.config import SNAPSHOTS_DIR

def save_portfolio_snapshot(snapshot_data: Dict[str, Any], base_dir: str = SNAPSHOTS_DIR) -> None:
    """Saves a detailed portfolio snapshot atomically."""
    try:
        os.makedirs(base_dir, exist_ok=True)
        
        timestamp = datetime.now()
        filename = f"portfolio_{timestamp.strftime('%Y%m%d_%H00')}.json"
        file_path = os.path.join(base_dir, filename)
        
        # Add metadata
        snapshot_data["timestamp"] = timestamp.isoformat()
        
        temp_path = f"{file_path}.tmp"
        with open(temp_path, "w") as f:
            json.dump(snapshot_data, f, indent=2)
        os.replace(temp_path, file_path)
        
        global_metrics.record_db_write()
        logger.info(f"Portfolio state snapshot persisted: {filename}")
    except Exception as e:
        logger.error(f"Failed to save portfolio state snapshot: {e}")

def load_latest_portfolio_snapshot(base_dir: str = SNAPSHOTS_DIR) -> Dict[str, Any]:
    """Loads the latest portfolio snapshot if available."""
    if not os.path.exists(base_dir):
        return {}
        
    try:
        files = [f for f in os.listdir(base_dir) if f.startswith("portfolio_") and f.endswith(".json")]
        if not files:
            return {}
            
        # Sort by filename which is timestamped
        files.sort()
        latest_file = os.path.join(base_dir, files[-1])
        
        with open(latest_file, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading latest portfolio snapshot: {e}")
        return {}
