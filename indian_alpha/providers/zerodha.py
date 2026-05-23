from typing import Dict, Any, List, Optional
import pandas as pd
from datetime import datetime, timedelta
from loguru import logger

from indian_alpha.providers.base import MarketDataProvider

class ZerodhaProvider(MarketDataProvider):
    """
    A Stub implementation of the MarketDataProvider for Zerodha Kite Connect.
    Allows easy drop-in migration by configuring API keys in the future.
    """
    def __init__(self, api_key: str = "stub_key", access_token: str = "stub_token"):
        self.api_key = api_key
        self.access_token = access_token
        logger.info("Initializing Zerodha Kite Connect provider stub.")

    async def fetch_ohlcv(
        self, 
        symbol: str, 
        start_date: str, 
        end_date: str, 
        interval: str = "1d"
    ) -> pd.DataFrame:
        logger.warning("ZerodhaProvider is in STUB mode. Redirecting to mock data.")
        # Return a mock empty dataframe with required schema
        cols = ["open", "high", "low", "close", "volume", "delivery_pct", "delivery_volume"]
        return pd.DataFrame(columns=cols)

    async def fetch_quote(self, symbol: str) -> Dict[str, Any]:
        logger.warning("ZerodhaProvider is in STUB mode.")
        return {
            "symbol": symbol,
            "price": 0.0,
            "volume": 0,
            "timestamp": datetime.now().isoformat(),
            "open": 0.0,
            "high": 0.0,
            "low": 0.0,
            "close": 0.0,
            "pct_change": 0.0
        }

    async def fetch_fundamentals(self, symbol: str) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "market_cap": 0.0,
            "pe_ratio": 0.0,
            "sector": "Unknown",
            "industry": "Unknown",
            "theme": "General",
            "long_name": symbol,
            "debt_to_equity": 0.0
        }

    async def fetch_delivery_data(self, symbol: str) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "delivery_pct": 50.0
        }

    async def fetch_index_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        return pd.DataFrame()

    async def fetch_sector_data(self) -> Dict[str, pd.DataFrame]:
        return {}

    async def fetch_market_breadth(self) -> Dict[str, Any]:
        return {
            "pct_above_50dma": 50.0,
            "advance_decline_ratio": 1.0,
            "advancing": 10,
            "declining": 10
        }

    async def fetch_vix(self) -> float:
        return 15.0
