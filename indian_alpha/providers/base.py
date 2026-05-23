from typing import Protocol, Dict, Any, List, Optional
import pandas as pd

class MarketDataProvider(Protocol):
    """
    Protocol defining the interface for all market data providers.
    Every provider (Yahoo, Zerodha, etc.) must implement these methods.
    """
    async def fetch_ohlcv(
        self, 
        symbol: str, 
        start_date: str, 
        end_date: str, 
        interval: str = "1d"
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data for a given symbol.
        Returns a pandas DataFrame with columns: open, high, low, close, volume, delivery_volume.
        """
        ...

    async def fetch_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch real-time or near real-time quote for a symbol.
        Returns:
            {
                "symbol": str,
                "price": float,
                "volume": int,
                "timestamp": str,
                "open": float,
                "high": float,
                "low": float,
                "close": float,
                "pct_change": float
            }
        """
        ...

    async def fetch_fundamentals(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch fundamental indicators for a symbol (PE, Market Cap, Sector, Industry, Debt-to-Equity, etc.)
        """
        ...

    async def fetch_delivery_data(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch delivery volume percentage for a stock.
        Returns:
            {
                "symbol": str,
                "delivery_pct": float  # 0.0 to 100.0
            }
        """
        ...

    async def fetch_index_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch index historical OHLCV (e.g. ^NSEI for NIFTY 50, ^BSESN for SENSEX).
        """
        ...

    async def fetch_sector_data(self) -> Dict[str, pd.DataFrame]:
        """
        Fetch sectoral index data to determine relative strength vs sector.
        """
        ...

    async def fetch_market_breadth(self) -> Dict[str, Any]:
        """
        Fetch market breadth metrics (Advance/Decline ratio, % of stocks above 50/200 DMA).
        """
        ...

    async def fetch_vix(self) -> float:
        """
        Fetch the current value of the India VIX index.
        """
        ...
