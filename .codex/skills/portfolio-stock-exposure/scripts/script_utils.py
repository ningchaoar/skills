from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation


def decimal_value(value, field_name: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if not result.is_finite():
        raise ValueError(f"{field_name} must be finite")
    return result


def decimal_to_float(value: Decimal) -> float:
    return float(value)


def infer_market(symbol: str) -> str | None:
    symbol = str(symbol).strip()
    if re.fullmatch(r"\d{6}", symbol):
        return "CN"
    if re.fullmatch(r"\d{5}", symbol):
        return "HK"
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9.-]{0,14}", symbol):
        return "US"
    return None


def merged_market(sources: list[dict]) -> str | None:
    markets = {
        str(source.get("market")).strip()
        for source in sources
        if isinstance(source, dict) and source.get("market")
    }
    if not markets:
        return None
    if len(markets) == 1:
        return next(iter(markets))
    return "/".join(sorted(markets))
