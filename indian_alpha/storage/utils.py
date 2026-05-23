import math
from typing import Any

def clean_json_data(obj: Any) -> Any:
    """
    Recursively converts NaN and Infinity floats to None to ensure 
    standard JSON compliance and prevent invalid JSON output.
    """
    if isinstance(obj, dict):
        return {k: clean_json_data(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_json_data(x) for x in obj]
    elif isinstance(obj, tuple):
        return tuple(clean_json_data(x) for x in obj)
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    return obj
