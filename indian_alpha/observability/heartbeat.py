import os
import json
from datetime import datetime
from indian_alpha.config import HEARTBEAT_FILE
from indian_alpha.observability.metrics import global_metrics

def write_heartbeat(mode: str, status: str = "healthy", heartbeat_path: str = HEARTBEAT_FILE) -> None:
    """Writes a heartbeat status file to verify scheduler health."""
    try:
        os.makedirs(os.path.dirname(heartbeat_path), exist_ok=True)
        
        heartbeat_data = {
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "mode": mode,
            "metrics": global_metrics.get_summary()
        }
        
        # Write atomically by writing to temporary file first and renaming it
        temp_path = f"{heartbeat_path}.tmp"
        with open(temp_path, "w") as f:
            json.dump(heartbeat_data, f, indent=2)
            
        os.replace(temp_path, heartbeat_path)
    except Exception as e:
        logger.error(f"Failed to write heartbeat status: {e}")
