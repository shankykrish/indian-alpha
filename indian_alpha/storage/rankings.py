import os
import json
from typing import List, Dict, Any
from datetime import datetime
from loguru import logger
from indian_alpha.observability.metrics import global_metrics

from indian_alpha.config import RANKINGS_FILE, SNAPSHOT_DIR

def load_rankings(file_path: str = RANKINGS_FILE) -> Dict[str, Any]:
    """Loads composite stock rankings."""
    if not os.path.exists(file_path):
        return {"last_updated": None, "rankings": []}
        
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading rankings from {file_path}: {e}")
        return {"last_updated": None, "rankings": []}

from indian_alpha.storage.utils import clean_json_data

def save_rankings(rankings_data: Dict[str, Any], file_path: str = RANKINGS_FILE) -> None:
    """Saves composite stock rankings atomically and takes a timestamped snapshot."""
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Add timestamp
        rankings_data["last_updated"] = datetime.now().isoformat()
        
        # Clean data to ensure JSON compliance (handles NaNs and Infs safely)
        rankings_data = clean_json_data(rankings_data)
        
        # Write atomically
        temp_path = f"{file_path}.tmp"
        with open(temp_path, "w") as f:
            json.dump(rankings_data, f, indent=2)
        os.replace(temp_path, file_path)
        
        global_metrics.record_db_write()
        
        # Take an hourly snapshot
        now = datetime.now()
        snapshot_filename = f"rankings_{now.strftime('%Y%m%d_%H00')}.json"
        snapshot_path = os.path.join(SNAPSHOT_DIR, snapshot_filename)
        
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)
        temp_snap = f"{snapshot_path}.tmp"
        with open(temp_snap, "w") as f:
            json.dump(rankings_data, f, indent=2)
        os.replace(temp_snap, snapshot_path)
        
    except Exception as e:
        logger.error(f"Failed to save rankings: {e}")
