import os
import asyncio
from datetime import datetime, time, date
import pytz
from loguru import logger
from typing import Dict, Any, List

class IndianMarketScheduler:
    """
    Timezone-aware and NSE Holiday-aware scheduling engine.
    Ensures correct execution mode transitions:
    - Active Market (09:00 - 15:30 IST, Mon-Fri)
    - Post-Market Analysis (15:30 - 18:00 IST, Mon-Fri)
    - Standby / Heartbeat (18:00 - 08:30 IST)
    - Weekend Workloads (Saturday: Walk-forward/Monte Carlo; Sunday: Summaries/Archival)
    """
    def __init__(self, timezone: str = "Asia/Kolkata"):
        self.tz = pytz.timezone(timezone)
        
        # Static NSE/BSE holidays list (2026/2027 generic projection)
        self.holidays = {
            date(2026, 1, 26),  # Republic Day
            date(2026, 3, 6),   # Holi
            date(2026, 4, 3),   # Good Friday
            date(2026, 4, 14),  # Ambedkar Jayanti
            date(2026, 5, 1),   # Maharashtra Day
            date(2026, 8, 15),  # Independence Day
            date(2026, 10, 2),  # Gandhi Jayanti
            date(2026, 11, 8),  # Diwali (Muhurat session is active)
            date(2026, 12, 25), # Christmas
        }

    def get_current_ist_time(self) -> datetime:
        """Returns current time localized to Asia/Kolkata."""
        return datetime.now(self.tz)

    def is_trading_day(self, current_dt: datetime) -> bool:
        """Checks if today is a trading day (Mon-Fri and not an NSE Holiday)."""
        current_date = current_dt.date()
        if current_dt.strftime("%A") not in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
            return False
        if current_date in self.holidays:
            # Note: Diwali Muhurat trading is handled as a special active hour, not a holiday
            if current_date.month == 11 and current_date.day == 8:
                return True
            return False
        return True

    def is_muhurat_trading_session(self, current_dt: datetime) -> bool:
        """
        Special Muhurat trading session detection (Diwali).
        Typically held on Diwali evening (e.g. 17:30 to 18:30 IST).
        """
        current_date = current_dt.date()
        # Assume Nov 8 is Muhurat trading day in 2026
        if current_date.month == 11 and current_date.day == 8:
            muhurat_start = time(17, 30)
            muhurat_end = time(18, 30)
            current_time = current_dt.time()
            return muhurat_start <= current_time <= muhurat_end
        return False

    def determine_execution_mode(self) -> str:
        """
        Analyzes the calendar and time clock to determine the current execution mode:
        Returns:
            "active_market", "post_market", "standby", "saturday_workload", "sunday_workload"
        """
        now_ist = self.get_current_ist_time()
        weekday = now_ist.strftime("%A")
        current_time = now_ist.time()

        # Check weekend workloads first
        if weekday == "Saturday":
            return "saturday_workload"
        elif weekday == "Sunday":
            return "sunday_workload"

        # Check special Muhurat trading session
        if self.is_muhurat_trading_session(now_ist):
            return "active_market"

        # Check standard trading days
        if not self.is_trading_day(now_ist):
            return "standby"

        # Trading day hours classification
        active_start = time(9, 0)
        active_end = time(15, 30)
        post_start = time(15, 30)
        post_end = time(18, 0)

        if active_start <= current_time < active_end:
            return "active_market"
        elif post_start <= current_time < post_end:
            return "post_market"
        else:
            return "standby"
