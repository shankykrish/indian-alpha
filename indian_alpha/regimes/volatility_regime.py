import pandas as pd
import numpy as np

def calculate_rolling_volatility(df: pd.DataFrame, window: int = 20) -> float:
    """
    Calculates rolling annualised volatility from daily close prices.
    Returns as percentage (e.g. 15.5 for 15.5%).
    """
    if df.empty or len(df) < window:
        return 15.0  # Return baseline
        
    try:
        # Check close column name
        close_col = "close" if "close" in df.columns else df.columns[0]
        returns = df[close_col].pct_change().dropna()
        daily_vol = returns.rolling(window).std().iloc[-1]
        
        # Annualise daily volatility assuming 252 trading days
        annualized_vol = daily_vol * np.sqrt(252) * 100.0
        
        if np.isnan(annualized_vol) or np.isinf(annualized_vol):
            return 15.0
            
        return float(annualized_vol)
    except Exception:
        return 15.0
