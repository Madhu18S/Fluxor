"""
Input validation utilities
"""

from typing import Optional, Tuple
import re
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class ValidationError(Exception):
    """Raised when validation fails"""
    pass


def validate_symbol(symbol: str) -> bool:
    """
    Validate trading symbol format
    Expected format: BTC/USD, ETH/USDC, etc.
    """
    if not symbol:
        raise ValidationError("Symbol cannot be empty")
    
    if not isinstance(symbol, str):
        raise ValidationError(f"Symbol must be string, got {type(symbol)}")
    
    # Check format: XXX/YYY
    pattern = r'^[A-Z]{2,10}/[A-Z]{2,10}$'
    if not re.match(pattern, symbol):
        raise ValidationError(f"Invalid symbol format: {symbol}. Expected format: BTC/USD")
    
    return True


def validate_price(price: float, min_price: float = 0, max_price: float = 1e10) -> bool:
    """
    Validate price value
    """
    if not isinstance(price, (int, float)):
        raise ValidationError(f"Price must be numeric, got {type(price)}")
    
    if price < min_price:
        raise ValidationError(f"Price {price} is below minimum {min_price}")
    
    if price > max_price:
        raise ValidationError(f"Price {price} exceeds maximum {max_price}")
    
    if price != price:  # NaN check
        raise ValidationError("Price is NaN")
    
    return True


def validate_quantity(quantity: float, min_qty: float = 0.00000001, max_qty: float = 1e8) -> bool:
    """
    Validate order quantity
    """
    if not isinstance(quantity, (int, float)):
        raise ValidationError(f"Quantity must be numeric, got {type(quantity)}")
    
    if quantity < min_qty:
        raise ValidationError(f"Quantity {quantity} below minimum {min_qty}")
    
    if quantity > max_qty:
        raise ValidationError(f"Quantity {quantity} exceeds maximum {max_qty}")
    
    return True


def validate_venue(venue: str, allowed_venues: Optional[list] = None) -> bool:
    """
    Validate venue name
    """
    if not venue or not isinstance(venue, str):
        raise ValidationError("Venue must be non-empty string")
    
    if allowed_venues and venue not in allowed_venues:
        raise ValidationError(f"Venue {venue} not in allowed list: {allowed_venues}")
    
    return True


def validate_percentage(value: float, name: str = "percentage") -> bool:
    """
    Validate percentage value (0-100 or 0-1)
    """
    if not isinstance(value, (int, float)):
        raise ValidationError(f"{name} must be numeric")
    
    if value < 0 or value > 1:
        if value < 0 or value > 100:
            raise ValidationError(f"{name} must be between 0 and 1 (or 0-100)")
    
    return True


def validate_timestamp(timestamp) -> bool:
    """
    Validate timestamp
    """
    from datetime import datetime
    
    if isinstance(timestamp, datetime):
        return True
    
    try:
        datetime.fromisoformat(str(timestamp))
        return True
    except:
        raise ValidationError(f"Invalid timestamp: {timestamp}")


def validate_spread(bid: float, ask: float) -> Tuple[bool, float]:
    """
    Validate bid-ask spread and return spread percentage
    """
    if bid <= 0 or ask <= 0:
        raise ValidationError("Bid and ask must be positive")
    
    if ask < bid:
        raise ValidationError(f"Ask price ({ask}) cannot be less than bid ({bid})")
    
    spread = (ask - bid) / bid if bid != 0 else 0
    return True, spread


def validate_api_credentials(api_key: str, api_secret: str) -> bool:
    """
    Basic validation of API credentials
    """
    if not api_key or not isinstance(api_key, str):
        raise ValidationError("API key is invalid or missing")
    
    if not api_secret or not isinstance(api_secret, str):
        raise ValidationError("API secret is invalid or missing")
    
    if len(api_key) < 10:
        raise ValidationError("API key appears too short")
    
    return True
