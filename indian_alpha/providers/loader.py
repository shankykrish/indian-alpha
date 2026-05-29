from typing import Optional
from indian_alpha.providers.base import MarketDataProvider
from indian_alpha.providers.yahoo import YahooFinanceProvider
from indian_alpha.providers.zerodha import ZerodhaProvider
from indian_alpha.storage.strategy_store import load_strategy

# Global cache of active provider to ensure consistent state/session management
_active_provider: Optional[MarketDataProvider] = None

def get_active_provider(force_refresh: bool = False) -> MarketDataProvider:
    """
    Dynamic factory that returns the active market data provider (Yahoo or Zerodha)
    configured in strategy.yaml. Reuses a singleton instance unless force_refresh is True.
    """
    global _active_provider
    if _active_provider is not None and not force_refresh:
        return _active_provider
        
    strat_cfg = load_strategy()
    provider_name = strat_cfg.get("market_data", {}).get("provider", "yahoo").lower()
    
    if provider_name == "zerodha":
        _active_provider = ZerodhaProvider()
    else:
        _active_provider = YahooFinanceProvider()
        
    return _active_provider

def reset_active_provider() -> None:
    """Resets the singleton provider instance (useful when dynamically switching configs or logging in)."""
    global _active_provider
    _active_provider = None
