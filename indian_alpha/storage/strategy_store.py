import os
import yaml
from typing import Dict, Any, Tuple
from loguru import logger
from indian_alpha.observability.metrics import global_metrics

from indian_alpha.config import STRATEGY_FILE, HISTORY_DIR

def load_strategy(file_path: str = STRATEGY_FILE) -> Dict[str, Any]:
    """Loads the active strategy variables from the YAML configuration."""
    if not os.path.exists(file_path):
        logger.error(f"Strategy file not found at {file_path}. System may fail to start.")
        return {}
        
    try:
        with open(file_path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error loading strategy from {file_path}: {e}")
        return {}

def save_strategy(
    strategy_data: Dict[str, Any], 
    file_path: str = STRATEGY_FILE, 
    archive: bool = True
) -> None:
    """
    Saves strategy variables atomically. 
    If archive is True, backs up the previous version to history/ directory first.
    """
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Archive previous file if it exists
        if archive and os.path.exists(file_path):
            try:
                old_strategy = load_strategy(file_path)
                old_version = old_strategy.get("version", "01")
                
                os.makedirs(HISTORY_DIR, exist_ok=True)
                backup_filename = f"strategy_v{old_version}.yaml"
                backup_path = os.path.join(HISTORY_DIR, backup_filename)
                
                # Copy current to backup
                with open(backup_path, "w") as bf:
                    yaml.safe_dump(old_strategy, bf, default_flow_style=False)
                logger.info(f"Archived previous strategy version {old_version} to {backup_path}")
            except Exception as ae:
                logger.error(f"Failed to archive previous strategy version: {ae}")
                
        # Write new strategy atomically
        temp_path = f"{file_path}.tmp"
        with open(temp_path, "w") as f:
            yaml.safe_dump(strategy_data, f, default_flow_style=False)
        os.replace(temp_path, file_path)
        
        global_metrics.record_db_write()
        logger.info(f"Strategy configuration successfully updated to version {strategy_data.get('version')}")
    except Exception as e:
        logger.error(f"Failed to save strategy: {e}")
