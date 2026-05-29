from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
import json

from indian_alpha.storage.snapshots import save_portfolio_snapshot, load_latest_portfolio_snapshot

INITIAL_CASH = 1000000.0  # 10 Lakhs INR baseline

class IndianEquitiesPortfolio:
    """
    Manages the paper trading portfolio account balances, active positions, 
    and sector concentration constraints for NSE/BSE equities.
    """
    def __init__(self, initial_cash: float = INITIAL_CASH):
        self.cash = initial_cash
        self.positions: Dict[str, Dict[str, Any]] = {}  # symbol -> position_info
        
        # Load state if a saved snapshot exists
        self.load_state()

    def load_state(self) -> None:
        """Loads latest portfolio snapshot from disk to ensure persistence."""
        snapshot = load_latest_portfolio_snapshot()
        if snapshot:
            self.cash = snapshot.get("cash", INITIAL_CASH)
            self.positions = snapshot.get("positions", {})
            logger.info(f"Restored portfolio state: Cash = Rs. {self.cash:,.2f}, Active Positions = {len(self.positions)}")
        else:
            logger.info(f"No snapshot found. Initializing portfolio with Rs. {self.cash:,.2f} cash.")

    def save_state(self, active_regime: str = "sideways") -> None:
        """Saves current state to snapshots folder."""
        equity = self.get_total_equity()
        snapshot = {
            "cash": self.cash,
            "positions": self.positions,
            "total_equity": equity,
            "active_regime": active_regime,
            "timestamp": datetime.now().isoformat()
        }
        save_portfolio_snapshot(snapshot)

    def get_total_equity(self) -> float:
        """Returns total portfolio value (cash + sum of market values of all holdings)."""
        positions_value = 0.0
        for sym, pos in self.positions.items():
            qty = pos.get("quantity")
            if qty is None:
                qty = 0
            price = pos.get("current_price")
            if price is None:
                price = pos.get("entry_price")
            if price is None:
                price = 0.0
            positions_value += qty * price
            
        cash = self.cash
        if cash is None:
            cash = 0.0
        return cash + positions_value

    def can_add_position(
        self, 
        symbol: str, 
        sector: str, 
        allocated_capital: float, 
        max_positions: int = 10,
        max_sector_exposure_pct: float = 30.0
    ) -> Tuple[bool, str]:
        """
        Validates whether a new position can be entered, checking:
        1. Max positions limit.
        2. Sufficient cash.
        3. Sector exposure limits.
        """
        import indian_alpha.portfolio as p
        # 1. Check max positions limit
        if len(self.positions) >= max_positions and symbol not in self.positions:
            return False, f"Maximum positions limit ({max_positions}) reached."

        # 2. Check sufficient cash
        if allocated_capital > self.cash:
            return False, f"Insufficient cash. Required: ₹{allocated_capital:,.2f}, Available: ₹{self.cash:,.2f}"

        # 3. Check sector exposure cap
        equity = self.get_total_equity()
        if equity <= 0.0:
            equity = 1000000.0
        sector_value = 0.0
        for sym, pos in self.positions.items():
            if pos.get("sector", "").upper() == sector.upper():
                qty = pos.get("quantity")
                if qty is None:
                    qty = 0
                price = pos.get("current_price")
                if price is None:
                    price = pos.get("entry_price")
                if price is None:
                    price = 0.0
                sector_value += qty * price
                
        new_sector_exposure_pct = ((sector_value + allocated_capital) / equity) * 100.0
        if new_sector_exposure_pct > max_sector_exposure_pct:
            return False, f"Sector cap limit exceeded. Sector '{sector}' exposure would be {new_sector_exposure_pct:.2f}% (Cap: {max_sector_exposure_pct}%)."

        return True, "Approved"

    def update_holding_price(self, symbol: str, current_price: float) -> None:
        """Updates the mark-to-market price of a holding."""
        import math
        if symbol in self.positions:
            if current_price is None or (isinstance(current_price, float) and math.isnan(current_price)) or current_price == 0.0:
                logger.warning(f"Invalid mark price update received for {symbol}: {current_price}. Preserving current state.")
                return
                
            self.positions[symbol]["current_price"] = current_price
            # Calculate current unrealized P&L
            qty = self.positions[symbol]["quantity"]
            entry_price = self.positions[symbol]["entry_price"]
            self.positions[symbol]["unrealized_pnl"] = (current_price - entry_price) * qty
            self.positions[symbol]["unrealized_pnl_pct"] = ((current_price - entry_price) / entry_price) * 100.0

    def enter_position(
        self, 
        symbol: str, 
        quantity: int, 
        price: float, 
        sector: str, 
        theme: str,
        execution_cost: float
    ) -> None:
        """Records entry of a paper trade position."""
        cost = quantity * price
        total_cost = cost + execution_cost
        
        self.cash -= total_cost
        
        self.positions[symbol] = {
            "symbol": symbol,
            "quantity": quantity,
            "entry_price": price,
            "current_price": price,
            "entry_time": datetime.now().isoformat(),
            "sector": sector,
            "theme": theme,
            "unrealized_pnl": 0.0,
            "unrealized_pnl_pct": 0.0
        }
        logger.info(f"Entered position {symbol}: {quantity} shares @ Rs. {price:.2f}. Total cost including brokerage: Rs. {total_cost:,.2f}")

    def exit_position(
        self, 
        symbol: str, 
        quantity: int, 
        price: float, 
        execution_cost: float
    ) -> Dict[str, Any]:
        """Records partial or full exit of a position."""
        if symbol not in self.positions:
            logger.error(f"Cannot exit position {symbol}: Not in holdings.")
            return {}
            
        pos = self.positions[symbol]
        qty_to_sell = min(quantity, pos["quantity"])
        
        revenue = qty_to_sell * price
        net_revenue = revenue - execution_cost
        
        self.cash += net_revenue
        
        entry_price = pos["entry_price"]
        pnl = (price - entry_price) * qty_to_sell
        pnl_pct = ((price - entry_price) / entry_price) * 100.0
        
        # Update remaining holdings
        pos["quantity"] -= qty_to_sell
        if pos["quantity"] <= 0:
            del self.positions[symbol]
            logger.info(f"Fully exited position {symbol}: sold {qty_to_sell} @ Rs. {price:.2f}. Pnl: Rs. {pnl:,.2f}")
        else:
            pos["unrealized_pnl"] = (pos["current_price"] - entry_price) * pos["quantity"]
            pos["unrealized_pnl_pct"] = ((pos["current_price"] - entry_price) / entry_price) * 100.0
            logger.info(f"Partially exited position {symbol}: sold {qty_to_sell} @ Rs. {price:.2f}. Remaining: {pos['quantity']}")
            
        return {
            "symbol": symbol,
            "quantity_sold": qty_to_sell,
            "entry_price": entry_price,
            "exit_price": price,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "execution_cost": execution_cost
        }
        
    def determine_regime_sizing(self, regime: str, risk_config: Dict[str, Any]) -> Tuple[int, float]:
        """
        Determines risk parameters dynamically based on classified market regime:
        Returns:
            (max_positions, position_size_pct)
        """
        base_max_pos = risk_config.get("max_positions", 10)
        base_pos_pct = risk_config.get("position_size_pct", 10.0)
        
        if regime == "bull_low_vol":
            return base_max_pos, base_pos_pct
        elif regime == "bull_high_vol":
            return base_max_pos - 2, base_pos_pct - 1.0  # e.g., max 8 positions, 9% size
        elif regime == "sideways":
            return 5, 5.0  # max 5 positions, 5% sizing
        elif regime == "recovery":
            return 6, 6.0  # conservative exposure
        elif regime == "bear":
            return 3, 3.0  # high cash conservation
        elif regime == "panic":
            return 0, 0.0  # 100% Cash preservation (no entries)
        else:
            return 5, 5.0
