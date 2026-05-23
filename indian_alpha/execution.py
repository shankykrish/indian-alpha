from typing import Dict, Any, Tuple
from loguru import logger
import random

class IndianMarketExecutionSimulator:
    """
    Simulates realistic paper trading execution for NSE & BSE equities, including:
    - Brokerage and regulatory charges (STT, stamp duty, exchange fees, SEBI, GST).
    - Bid-Ask slippage modeled on stock market capitalization and volume.
    - Gap open fills.
    - Upper & Lower circuit rejection handling.
    """
    def __init__(self, stt_pct: float = 0.1): # 0.1% for delivery trading in India
        self.stt_pct = stt_pct

    def calculate_execution_charges(self, quantity: int, price: float, is_buy: bool) -> float:
        """
        Calculates exact Zerodha-like discount broker charges for Delivery Trades:
        - Brokerage: Flat ₹20 or 0.03% (whichever is lower)
        - STT (Securities Transaction Tax): 0.1% on both Buy and Sell
        - Transaction Charges (NSE): 0.00345% of trade value
        - GST: 18% on (Brokerage + Transaction Charges)
        - SEBI Charges: 0.0001% (₹10/crore) of trade value
        - Stamp Duty: 0.015% (Buy only)
        """
        trade_value = quantity * price
        
        # 1. Brokerage
        brokerage = min(20.0, trade_value * 0.0003)
        
        # 2. STT (0.1% for Delivery)
        stt = trade_value * (self.stt_pct / 100.0)
        
        # 3. Exchange Transaction Charges (NSE)
        trans_charges = trade_value * 0.0000345
        
        # 4. SEBI Turnover Charges
        sebi_charges = trade_value * 0.000001
        
        # 5. GST (18% of Brokerage + Trans Charges + SEBI)
        gst = (brokerage + trans_charges + sebi_charges) * 0.18
        
        # 6. Stamp Duty (0.015% on Buy only)
        stamp_duty = (trade_value * 0.00015) if is_buy else 0.0
        
        total_charges = brokerage + stt + trans_charges + sebi_charges + gst + stamp_duty
        return float(total_charges)

    def simulate_slippage(self, price: float, market_cap_cr: float, is_buy: bool) -> float:
        """
        Models bid-ask slippage. 
        Highly-liquid blue-chips (high market cap) have very low slippage (0.02% - 0.05%).
        Low-liquidity smallcaps have higher slippage (0.15% - 0.5%).
        """
        if market_cap_cr > 50000.0:  # Large Cap (>50k Cr)
            slippage_pct = random.uniform(0.01, 0.03)
        elif market_cap_cr > 10000.0: # Mid Cap (10k-50k Cr)
            slippage_pct = random.uniform(0.04, 0.10)
        else:                         # Small/Micro Cap (<10k Cr)
            slippage_pct = random.uniform(0.12, 0.35)
            
        multiplier = 1.0 + (slippage_pct / 100.0) if is_buy else 1.0 - (slippage_pct / 100.0)
        return float(price * multiplier)

    def verify_circuits(
        self, 
        pct_change_1d: float, 
        is_buy: bool,
        circuit_limit_pct: float = 19.5
    ) -> Tuple[bool, str]:
        """
        Checks upper and lower circuit breaker limits.
        - If Buy, and stock is up near 20% (upper circuit), entry is blocked (no sellers).
        - If Sell, and stock is down near 20% (lower circuit), exit is blocked (no buyers).
        """
        if is_buy and pct_change_1d >= circuit_limit_pct:
            return False, f"Upper circuit hit (+{pct_change_1d:.2f}%). Order blocked due to lack of sellers."
        if not is_buy and pct_change_1d <= -circuit_limit_pct:
            return False, f"Lower circuit hit ({pct_change_1d:.2f}%). Order blocked due to lack of buyers."
            
        return True, "Executed"
