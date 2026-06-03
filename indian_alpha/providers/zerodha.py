import os
import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from loguru import logger
from kiteconnect import KiteConnect

from indian_alpha.providers.base import MarketDataProvider

class ZerodhaProvider(MarketDataProvider):
    """
    Implements the MarketDataProvider interface using Zerodha Kite Connect API.
    Handles dynamic daily OAuth sessions, local caching of instrument tokens,
    real-time quotes, and high-precision data integration.
    """
    def __init__(self):
        self.api_key = os.getenv("ZERODHA_API_KEY")
        self.api_secret = os.getenv("ZERODHA_API_SECRET")
        self.access_token = None
        self.kite: Optional[KiteConnect] = None
        self.session_created_at: Optional[datetime] = None
        
        import pytz
        tz = pytz.timezone("Asia/Kolkata")
        self._last_session_check = datetime.now(tz)
        
        # Load persistent credentials session if active
        self._load_cached_session()
        
    def get_login_url(self) -> str:
        """Generates the login URL to fetch the request_token for OAuth authorization."""
        if not self.api_key:
            logger.error("ZERODHA_API_KEY is not set. Cannot generate Zerodha Login URL.")
            return ""
        return f"https://kite.zerodha.com/connect/login?api_key={self.api_key}&v=3"

    def generate_session(self, request_token: str) -> bool:
        """
        Exchanges the request_token obtained from redirect for an access_token.
        Caches the token locally to ensure background daemons run seamlessly.
        """
        if not self.api_key or not self.api_secret:
            logger.error("API Key or API Secret is missing in environment. Authentication failed.")
            return False
            
        try:
            logger.info(f"Exchanging request token with Zerodha Kite Connect...")
            kite_client = KiteConnect(api_key=self.api_key)
            session_data = kite_client.generate_session(request_token, api_secret=self.api_secret)
            
            import pytz
            tz = pytz.timezone("Asia/Kolkata")
            self.access_token = session_data["access_token"]
            self.session_created_at = datetime.now(tz)
            self.kite = kite_client
            self.kite.set_access_token(self.access_token)
            
            # Save token to persistent JSON state cache
            from indian_alpha.config import BASE_STATE_DIR
            session_file = os.path.join(BASE_STATE_DIR, "zerodha_session.json")
            cache_data = {
                "access_token": self.access_token,
                "created_at": self.session_created_at.isoformat()
            }
            with open(session_file, "w") as f:
                json.dump(cache_data, f, indent=2)
                
            logger.info("Successfully established active Zerodha session and persisted token cache.")
            return True
        except Exception as e:
            logger.error(f"Failed to generate Zerodha Kite session: {e}")
            return False

    def is_connected(self) -> bool:
        """Returns True if the Zerodha Kite Connect client is actively authenticated."""
        import pytz
        tz = pytz.timezone("Asia/Kolkata")
        now = datetime.now(tz)
        
        # Check if the in-memory session is older than the daily 6:00 AM IST expiration boundary
        session_expired = True
        if self.session_created_at is not None:
            session_created_at_ist = self.session_created_at.astimezone(tz) if self.session_created_at.tzinfo else self.session_created_at.replace(tzinfo=tz)
            six_am_today = datetime(now.year, now.month, now.day, 6, 0, 0, tzinfo=tz)
            if now >= six_am_today:
                session_expired = session_created_at_ist < six_am_today
            else:
                six_am_yesterday = six_am_today - timedelta(days=1)
                session_expired = session_created_at_ist < six_am_yesterday

        # Check the disk if we don't have a token, if it expired,
        # or periodically (every 60s) to see if another process (like Streamlit) refreshed it.
        should_check_disk = self.kite is None or self.access_token is None or session_expired
        
        if not should_check_disk:
            # Periodic check for token updates from other processes
            last_check = self._last_session_check
            if last_check.tzinfo is None:
                last_check = last_check.replace(tzinfo=tz)
            if not hasattr(self, '_last_session_check') or (now - last_check).total_seconds() > 60:
                self._last_session_check = now
                from indian_alpha.config import BASE_STATE_DIR
                session_file = os.path.join(BASE_STATE_DIR, "zerodha_session.json")
                if os.path.exists(session_file):
                    try:
                        with open(session_file, "r") as f:
                            cache_data = json.load(f)
                        disk_token = cache_data.get("access_token")
                        if disk_token and disk_token != self.access_token:
                            logger.info("Detected new Zerodha session token on disk. Hot-reloading...")
                            should_check_disk = True
                    except Exception:
                        pass

        if should_check_disk:
            last_check = self._last_session_check
            if last_check.tzinfo is None:
                last_check = last_check.replace(tzinfo=tz)
            time_since_check = (now - last_check).total_seconds() if hasattr(self, '_last_session_check') else 999.0
            if time_since_check > 5:  # 5-second cooldown to prevent spamming disk reads during a single loop scan
                self._last_session_check = now
                self._load_cached_session()
            
            # Re-evaluate session expiration status after reload
            if self.session_created_at is not None:
                session_created_at_ist = self.session_created_at.astimezone(tz) if self.session_created_at.tzinfo else self.session_created_at.replace(tzinfo=tz)
                six_am_today = datetime(now.year, now.month, now.day, 6, 0, 0, tzinfo=tz)
                if now >= six_am_today:
                    session_expired = session_created_at_ist < six_am_today
                else:
                    six_am_yesterday = six_am_today - timedelta(days=1)
                    session_expired = session_created_at_ist < six_am_yesterday
            else:
                session_expired = True
                
        return self.kite is not None and self.access_token is not None and not session_expired

    def _load_cached_session(self) -> None:
        """Loads and validates a cached daily Zerodha session token from disk."""
        from indian_alpha.config import BASE_STATE_DIR
        session_file = os.path.join(BASE_STATE_DIR, "zerodha_session.json")
        
        import pytz
        tz = pytz.timezone("Asia/Kolkata")
        now = datetime.now(tz)
        
        if not os.path.exists(session_file):
            logger.warning("No Zerodha session file found. System is waiting for initial login.")
            today_str = now.strftime("%Y-%m-%d")
            if getattr(self, "_last_expiry_alert_date", None) != today_str:
                self._last_expiry_alert_date = today_str
                from indian_alpha.observability.alerts import send_alert_sync
                send_alert_sync(
                    "No Zerodha session file found. System is waiting for initial login. Please authenticate at https://shanky-alpha.duckdns.org/",
                    level="WARNING"
                )
            return
            
        try:
            with open(session_file, "r") as f:
                cache_data = json.load(f)
                
            created_at_str = cache_data.get("created_at")
            if not created_at_str:
                return
                
            created_at = datetime.fromisoformat(created_at_str)
            created_at_ist = created_at.astimezone(tz) if created_at.tzinfo else created_at.replace(tzinfo=tz)
            
            # Zerodha API sessions expire daily at 6:00 AM IST
            six_am_today = datetime(now.year, now.month, now.day, 6, 0, 0, tzinfo=tz)
            
            # Determine validity boundary based on current time in IST
            is_valid = False
            if now >= six_am_today:
                is_valid = created_at_ist >= six_am_today
            else:
                six_am_yesterday = six_am_today - timedelta(days=1)
                is_valid = created_at_ist >= six_am_yesterday
                
            if is_valid:
                self.access_token = cache_data.get("access_token")
                self.session_created_at = created_at_ist
                if self.api_key and self.access_token:
                    self.kite = KiteConnect(api_key=self.api_key)
                    self.kite.set_access_token(self.access_token)
                    logger.info("Re-authenticated actively using cached daily Zerodha session token.")
            else:
                self.access_token = None
                self.kite = None
                self.session_created_at = None
                logger.warning("Cached Zerodha session token has expired. A new daily login is required.")
                today_str = now.strftime("%Y-%m-%d")
                if getattr(self, "_last_expiry_alert_date", None) != today_str:
                    self._last_expiry_alert_date = today_str
                    from indian_alpha.observability.alerts import send_alert_sync
                    send_alert_sync(
                        "Cached Zerodha session token has expired. A new daily login is required. Please authenticate at https://shanky-alpha.duckdns.org/",
                        level="WARNING"
                    )
        except Exception as e:
            logger.error(f"Failed to parse cached Zerodha session token: {e}")

    def _clear_session(self) -> None:
        """Clears both in-memory credentials and deletes the cached session file on disk."""
        logger.warning("Clearing and removing Zerodha session from memory and disk.")
        self.access_token = None
        self.kite = None
        self.session_created_at = None
        
        from indian_alpha.config import BASE_STATE_DIR
        session_file = os.path.join(BASE_STATE_DIR, "zerodha_session.json")
        if os.path.exists(session_file):
            try:
                os.remove(session_file)
                logger.info("Successfully deleted invalid Zerodha session file from disk.")
            except Exception as e:
                logger.error(f"Failed to delete invalid Zerodha session file from disk: {e}")

    def _load_or_fetch_instrument_tokens(self) -> Dict[str, int]:
        """
        Loads the daily mapping of ticker symbols to Zerodha instrument tokens.
        Downloads and caches the list locally from the Kite API once a day to ensure optimal speed.
        """
        from indian_alpha.config import BASE_STATE_DIR
        token_cache_file = os.path.join(BASE_STATE_DIR, "kite_tokens_cache.json")
        
        # Check cache validity (must be younger than 24 hours)
        if os.path.exists(token_cache_file):
            try:
                mtime = os.path.getmtime(token_cache_file)
                if datetime.now().timestamp() - mtime < 86400:
                    with open(token_cache_file, "r") as f:
                        return json.load(f)
            except Exception as e:
                logger.error(f"Failed to read instrument token cache: {e}")
                
        if not self.kite:
            logger.warning("Zerodha client is unauthenticated. Cannot fetch instrument token mappings.")
            return {}
            
        try:
            logger.info("Fetching daily instrument token definitions from Zerodha API...")
            instruments = self.kite.instruments("NSE")
            token_map = {}
            for inst in instruments:
                if inst.get("segment") in ["nse", "NSE"] and inst.get("instrument_type") == "EQ":
                    symbol = inst["tradingsymbol"]
                    token_map[symbol] = int(inst["instrument_token"])
                    token_map[f"{symbol}.NS"] = int(inst["instrument_token"])
                    
            with open(token_cache_file, "w") as f:
                json.dump(token_map, f, indent=2)
            logger.info(f"Successfully cached {len(token_map)} equity instrument tokens.")
            return token_map
        except Exception as e:
            logger.error(f"Failed to query daily instruments list from Zerodha Kite: {e}")
            return {}

    async def fetch_ohlcv(
        self, 
        symbol: str, 
        start_date: str, 
        end_date: str, 
        interval: str = "1d"
    ) -> pd.DataFrame:
        """Fetches historical price candles from Zerodha and overlays EOD delivery percentage."""
        if not self.is_connected():
            logger.warning(f"Zerodha is not connected. Reverting to Yahoo fallback for {symbol} historical scan.")
            from indian_alpha.providers.yahoo import YahooFinanceProvider
            fallback = YahooFinanceProvider()
            return await fallback.fetch_ohlcv(symbol, start_date, end_date, interval)
            
        try:
            token_map = self._load_or_fetch_instrument_tokens()
            clean_sym = symbol.strip().upper().replace(".NS", "")
            token = token_map.get(clean_sym)
            
            if not token:
                logger.warning(f"Symbol {symbol} not recognized in Zerodha equities. Trying Yahoo.")
                from indian_alpha.providers.yahoo import YahooFinanceProvider
                fallback = YahooFinanceProvider()
                return await fallback.fetch_ohlcv(symbol, start_date, end_date, interval)
                
            from_dt = datetime.strptime(start_date, "%Y-%m-%d")
            to_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            kite_interval = "day"
            if interval == "1m":
                kite_interval = "minute"
                
            def _fetch():
                return self.kite.historical_data(token, from_dt, to_dt, kite_interval)
                
            records = await asyncio.to_thread(_fetch)
            if not records:
                return pd.DataFrame()
                
            df = pd.DataFrame(records)
            df = df.rename(columns={
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "volume"
            })
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                df = df.set_index("date")
                
            # Inject EOD delivery percentage dynamically
            from indian_alpha.providers.yahoo import YahooFinanceProvider
            yahoo = YahooFinanceProvider()
            df = await yahoo.inject_delivery_data(df, symbol)
            return df
        except Exception as e:
            logger.error(f"Error fetching OHLCV data from Zerodha for {symbol}: {e}")
            if any(err in str(e).lower() for err in ["access_token", "api_key", "incorrect", "token"]):
                self._clear_session()
                from indian_alpha.observability.alerts import send_alert
                await send_alert(
                    f"Zerodha Kite API session has expired or is invalid. Gracefully fell back to Yahoo Finance feed for historical scan of {symbol}. Please authenticate at https://shanky-alpha.duckdns.org/",
                    level="WARNING"
                )
            from indian_alpha.providers.yahoo import YahooFinanceProvider
            fallback = YahooFinanceProvider()
            return await fallback.fetch_ohlcv(symbol, start_date, end_date, interval)

    async def fetch_quote(self, symbol: str) -> Dict[str, Any]:
        """Queries real-time close, high, low, open, and volume from Zerodha."""
        if not self.is_connected():
            from indian_alpha.providers.yahoo import YahooFinanceProvider
            fallback = YahooFinanceProvider()
            return await fallback.fetch_quote(symbol)
            
        try:
            token_map = self._load_or_fetch_instrument_tokens()
            clean_sym = symbol.strip().upper().replace(".NS", "")
            token = token_map.get(clean_sym)
            
            if not token:
                from indian_alpha.providers.yahoo import YahooFinanceProvider
                fallback = YahooFinanceProvider()
                return await fallback.fetch_quote(symbol)
                
            def _fetch():
                return self.kite.quote(f"NSE:{clean_sym}")
                
            data = await asyncio.to_thread(_fetch)
            key = f"NSE:{clean_sym}"
            if key not in data:
                from indian_alpha.providers.yahoo import YahooFinanceProvider
                fallback = YahooFinanceProvider()
                return await fallback.fetch_quote(symbol)
                
            quote_data = data[key]
            last_price = quote_data.get("last_price", 0.0)
            ohlc = quote_data.get("ohlc", {})
            net_change = quote_data.get("net_change", 0.0)
            close_val = ohlc.get("close", last_price)
            
            pct_change = 0.0
            if close_val > 0:
                pct_change = (net_change / close_val) * 100.0 if net_change != 0 else 0.0
                
            return {
                "symbol": symbol,
                "price": float(last_price),
                "volume": int(quote_data.get("volume", 0)),
                "timestamp": datetime.now().isoformat(),
                "open": float(ohlc.get("open", last_price)),
                "high": float(ohlc.get("high", last_price)),
                "low": float(ohlc.get("low", last_price)),
                "close": float(close_val),
                "pct_change": float(pct_change)
            }
        except Exception as e:
            logger.error(f"Failed to fetch live quote from Zerodha for {symbol}: {e}")
            if any(err in str(e).lower() for err in ["access_token", "api_key", "incorrect", "token"]):
                self._clear_session()
                from indian_alpha.observability.alerts import send_alert
                await send_alert(
                    f"Zerodha Kite API session has expired or is invalid. Gracefully fell back to Yahoo Finance feed for live quote of {symbol}. Please authenticate at https://shanky-alpha.duckdns.org/",
                    level="WARNING"
                )
            from indian_alpha.providers.yahoo import YahooFinanceProvider
            fallback = YahooFinanceProvider()
            return await fallback.fetch_quote(symbol)

    async def fetch_fundamentals(self, symbol: str) -> Dict[str, Any]:
        """Loads fundamental metrics (leveraging cached Yahoo Finance fundamentals mapping)."""
        from indian_alpha.providers.yahoo import YahooFinanceProvider
        yahoo = YahooFinanceProvider()
        return await yahoo.fetch_fundamentals(symbol)

    async def fetch_delivery_data(self, symbol: str) -> Dict[str, Any]:
        """Scrapes or calculates authentic delivery volume metrics."""
        from indian_alpha.providers.yahoo import YahooFinanceProvider
        yahoo = YahooFinanceProvider()
        return await yahoo.fetch_delivery_data(symbol)

    async def fetch_index_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetches historical price curves for benchmark indexes (falling back to stable Yahoo symbols)."""
        from indian_alpha.providers.yahoo import YahooFinanceProvider
        yahoo = YahooFinanceProvider()
        return await yahoo.fetch_index_data(symbol, start_date, end_date)

    async def fetch_sector_data(self) -> Dict[str, pd.DataFrame]:
        """Loads sectoral benchmark datasets."""
        from indian_alpha.providers.yahoo import YahooFinanceProvider
        yahoo = YahooFinanceProvider()
        return await yahoo.fetch_sector_data()

    async def fetch_market_breadth(self) -> Dict[str, Any]:
        """Computes breadth metrics across selected equity constituents."""
        from indian_alpha.providers.yahoo import YahooFinanceProvider
        yahoo = YahooFinanceProvider()
        return await yahoo.fetch_market_breadth()

    async def fetch_vix(self) -> float:
        """Pulls the latest volatility index curve."""
        if not self.is_connected():
            from indian_alpha.providers.yahoo import YahooFinanceProvider
            fallback = YahooFinanceProvider()
            return await fallback.fetch_vix()
            
        try:
            def _fetch():
                return self.kite.quote("NSE:INDIA VIX")
            res = await asyncio.to_thread(_fetch)
            vix_val = res.get("NSE:INDIA VIX", {}).get("last_price")
            if vix_val:
                return float(vix_val)
        except Exception as e:
            logger.warning(f"Failed to fetch India VIX from Zerodha Kite Connect: {e}")
            if any(err in str(e).lower() for err in ["access_token", "api_key", "incorrect", "token"]):
                self._clear_session()
                from indian_alpha.observability.alerts import send_alert
                await send_alert(
                    "Zerodha Kite API session has expired or is invalid. Gracefully fell back to Yahoo Finance feed for India VIX. Please authenticate at https://shanky-alpha.duckdns.org/",
                    level="WARNING"
                )
        from indian_alpha.providers.yahoo import YahooFinanceProvider
        fallback = YahooFinanceProvider()
        return await fallback.fetch_vix()
