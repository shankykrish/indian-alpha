import os
import json
from typing import List, Dict, Any
from datetime import datetime
from loguru import logger
from indian_alpha.observability.metrics import global_metrics

from indian_alpha.config import HYPOTHESES_FILE

def load_hypotheses(file_path: str = HYPOTHESES_FILE) -> List[Dict[str, Any]]:
    """Loads all learning hypotheses logged by the self-learning reflection engine."""
    if not os.path.exists(file_path):
        return []
        
    hypotheses = []
    try:
        with open(file_path, "r") as f:
            for line in f:
                line_str = line.strip()
                if not line_str or line_str.startswith("#"):
                    continue
                try:
                    hyp = json.loads(line_str)
                    hypotheses.append(hyp)
                except json.JSONDecodeError as je:
                    logger.warning(f"Skipping malformed hypothesis line: {line_str}. Error: {je}")
    except Exception as e:
        logger.error(f"Error loading hypotheses from {file_path}: {e}")
        
    return hypotheses

from indian_alpha.storage.utils import clean_json_data

def save_hypothesis(hypothesis: Dict[str, Any], file_path: str = HYPOTHESES_FILE) -> None:
    """Appends a new reflection hypothesis to the JSONL log file atomically."""
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Ensure timestamp is set
        if "timestamp" not in hypothesis:
            hypothesis["timestamp"] = datetime.now().isoformat()
            
        # Clean data to ensure JSON compliance (handles NaNs and Infs safely)
        hypothesis = clean_json_data(hypothesis)
            
        with open(file_path, "a") as f:
            f.write(json.dumps(hypothesis) + "\n")
            
        global_metrics.record_db_write()
        logger.info(f"Hypothesis saved successfully: {hypothesis.get('variable')} changed from {hypothesis.get('old_value')} to {hypothesis.get('new_value')}")
    except Exception as e:
        logger.error(f"Failed to save hypothesis: {e}")
