import time
from typing import Dict, Any
from loguru import logger

class MetricsTracker:
    """Simple class to track operational metrics such as latencies and success rates."""
    def __init__(self):
        self.metrics: Dict[str, Any] = {
            "api_calls": 0,
            "api_errors": 0,
            "total_execution_time": 0.0,
            "scans_completed": 0,
            "db_writes": 0
        }

    def record_api_call(self, success: bool = True) -> None:
        self.metrics["api_calls"] += 1
        if not success:
            self.metrics["api_errors"] += 1

    def record_scan(self) -> None:
        self.metrics["scans_completed"] += 1

    def record_db_write(self) -> None:
        self.metrics["db_writes"] += 1

    def get_summary(self) -> Dict[str, Any]:
        return self.metrics.copy()
        
global_metrics = MetricsTracker()
