import pandas as pd
from typing import Dict, Any, List
from loguru import logger

def calculate_sector_momentum(sector_dfs: Dict[str, pd.DataFrame]) -> Dict[str, float]:
    """
    Calculates relative momentum scores for each sector based on recent 20-day returns.
    Returns:
        {"NIFTY_BANK": 12.5, "NIFTY_IT": -2.1, ...}
    """
    scores = {}
    for name, df in sector_dfs.items():
        if df.empty or len(df) < 20:
            scores[name] = 0.0
            continue
        try:
            close_col = "close" if "close" in df.columns else df.columns[0]
            ret_20d = ((df[close_col].iloc[-1] - df[close_col].iloc[-20]) / df[close_col].iloc[-20]) * 100.0
            scores[name] = float(ret_20d)
        except Exception as e:
            logger.error(f"Error calculating sector momentum for {name}: {e}")
            scores[name] = 0.0
            
    return scores

def get_sector_rankings(sector_scores: Dict[str, float]) -> List[str]:
    """Returns sector names sorted by their momentum scores, descending."""
    return sorted(sector_scores, key=sector_scores.get, reverse=True)
