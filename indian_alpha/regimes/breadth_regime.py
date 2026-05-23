from typing import Dict, Any
from loguru import logger

def classify_breadth_state(breadth_data: Dict[str, Any]) -> str:
    """
    Classifies the breadth of the market as bullish, neutral, or bearish.
    Factors in % above 50 DMA and the Advance/Decline ratio.
    """
    pct_above_50dma = breadth_data.get("pct_above_50dma", 50.0)
    ad_ratio = breadth_data.get("advance_decline_ratio", 1.0)
    
    if pct_above_50dma > 75.0 or (pct_above_50dma > 60.0 and ad_ratio > 1.5):
        return "BULLISH"
    elif pct_above_50dma < 30.0 or (pct_above_50dma < 40.0 and ad_ratio < 0.6):
        return "BEARISH"
    else:
        return "NEUTRAL"
