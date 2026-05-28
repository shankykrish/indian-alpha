import os
import asyncio
from datetime import datetime, time, date, timedelta
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
        
        # Static NSE/BSE holidays list (2026 generic calendar)
        self.holidays = {
            date(2026, 1, 26),  # Republic Day
            date(2026, 3, 3),   # Holi
            date(2026, 3, 26),  # Shri Ram Navami
            date(2026, 3, 31),  # Shri Mahavir Jayanti
            date(2026, 4, 3),   # Good Friday
            date(2026, 4, 14),  # Dr. Baba Saheb Ambedkar Jayanti
            date(2026, 5, 1),   # Maharashtra Day
            date(2026, 5, 28),  # Bakri Id
            date(2026, 6, 26),  # Muharram
            date(2026, 8, 15),  # Independence Day (Saturday)
            date(2026, 9, 14),  # Ganesh Chaturthi
            date(2026, 10, 2),  # Mahatma Gandhi Jayanti
            date(2026, 10, 20), # Dussehra
            date(2026, 11, 8),  # Diwali (Muhurat session is active)
            date(2026, 11, 10), # Diwali-Balipratipada
            date(2026, 11, 24), # Guru Nanak Jayanti
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

    def get_next_trigger_time(self) -> datetime:
        """
        Calculates the absolute datetime of the very next execution tick.
        During active trading day (09:00 - 15:30 IST): ticks every 30 mins (09:00, 09:30, ..., 15:00) and a final one at 15:25.
        Post-market: runs once at 15:35.
        Weekend/Standby: runs once daily at 09:00 AM.
        """
        now = self.get_current_ist_time()
        
        # Helper to construct a datetime on a given date
        def at_time(d, h: int, m: int) -> datetime:
            return self.tz.localize(datetime.combine(d, time(h, m, 0)))

        weekday = now.strftime("%A")
        
        # 1. If it's Saturday
        if weekday == "Saturday":
            target = at_time(now.date(), 9, 0)
            if now >= target:
                target = at_time(now.date() + timedelta(days=1), 9, 0)
            return target
            
        # 2. If it's Sunday
        if weekday == "Sunday":
            target = at_time(now.date(), 9, 0)
            if now >= target:
                target = at_time(now.date() + timedelta(days=1), 9, 0)
            return target

        # 3. It is a weekday (Mon-Fri)
        if not self.is_trading_day(now):
            target = at_time(now.date(), 9, 0)
            if now >= target:
                target = at_time(now.date() + timedelta(days=1), 9, 0)
            return target

        # Today is a trading day!
        # Define milestones
        market_open = at_time(now.date(), 9, 0)
        market_close_scan = at_time(now.date(), 15, 25)
        post_market_time = at_time(now.date(), 15, 35)
        
        if now < market_open:
            return market_open
            
        if market_open <= now < market_close_scan:
            current_minute = now.minute
            if current_minute < 30:
                next_tick = at_time(now.date(), now.hour, 30)
            else:
                next_hour = now.hour + 1
                if next_hour >= 24:
                    next_tick = at_time(now.date() + timedelta(days=1), 0, 0)
                else:
                    next_tick = at_time(now.date(), next_hour, 0)
            
            if next_tick >= market_close_scan:
                return market_close_scan
            return next_tick
            
        if market_close_scan <= now < post_market_time:
            return post_market_time
            
        return at_time(now.date() + timedelta(days=1), 9, 0)
