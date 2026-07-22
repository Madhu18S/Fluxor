"""
General utility helper functions
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json


def calculate_roi(initial: float, final: float) -> float:
    """
    Calculate return on investment percentage
    """
    if initial == 0:
        return 0
    return ((final - initial) / initial) * 100


def calculate_cagr(starting_value: float, ending_value: float, years: float) -> float:
    """
    Calculate Compound Annual Growth Rate
    """
    if starting_value <= 0 or years <= 0:
        return 0
    return (pow(ending_value / starting_value, 1 / years) - 1) * 100


def format_currency(value: float, decimals: int = 2, symbol: str = "$") -> str:
    """
    Format value as currency string
    """
    return f"{symbol}{value:,.{decimals}f}"


def format_percentage(value: float, decimals: int = 2) -> str:
    """
    Format value as percentage string
    """
    return f"{value*100:.{decimals}f}%"


def format_basis_points(value: float) -> str:
    """
    Format value as basis points (1 bps = 0.01%)
    """
    bps = value * 10000
    return f"{bps:.2f} bps"


def timestamp_to_readable(timestamp: datetime) -> str:
    """
    Convert timestamp to readable format
    """
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def get_time_remaining(deadline: datetime) -> str:
    """
    Get human-readable time remaining until deadline
    """
    remaining = deadline - datetime.utcnow()
    
    if remaining.total_seconds() <= 0:
        return "Expired"
    
    days = remaining.days
    hours, remainder = divmod(remaining.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 and days == 0:
        parts.append(f"{seconds}s")
    
    return " ".join(parts)


def batch_list(items: List, batch_size: int) -> List[List]:
    """
    Split list into batches
    """
    return [items[i:i + batch_size] for i in range(0, len(items), batch_size)]


def deep_merge_dicts(dict1: Dict, dict2: Dict) -> Dict:
    """
    Recursively merge two dictionaries
    """
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    
    return result


def flatten_dict(d: Dict, parent_key: str = '', sep: str = '_') -> Dict:
    """
    Flatten nested dictionary
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def safe_dict_get(d: Dict, keys: List[str], default: Any = None) -> Any:
    """
    Safely get nested dictionary value
    Example: safe_dict_get(data, ['market', 'prices', 'BTC'], default=0)
    """
    value = d
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return default
    return value if value is not None else default


def retry_async(max_attempts: int = 3, backoff: float = 1.0):
    """
    Decorator for retrying async functions with exponential backoff
    """
    import asyncio
    from functools import wraps
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    wait_time = backoff ** attempt
                    await asyncio.sleep(wait_time)
            return None
        return wrapper
    return decorator


def convert_to_base_units(amount: float, decimals: int) -> int:
    """
    Convert amount to base units (similar to wei in Ethereum)
    Example: 1.5 BTC with 8 decimals = 150000000
    """
    return int(amount * (10 ** decimals))


def convert_from_base_units(amount: int, decimals: int) -> float:
    """
    Convert from base units to display units
    Example: 150000000 wei with 8 decimals = 1.5 BTC
    """
    return amount / (10 ** decimals)


def parse_json_safe(json_str: str, default: Any = None) -> Any:
    """
    Safely parse JSON string
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default
