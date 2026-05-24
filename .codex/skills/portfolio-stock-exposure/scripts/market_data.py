from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode
from urllib.request import Request, urlopen


EASTMONEY_QUOTE_URL = "https://push2.eastmoney.com/api/qt/stock/get"
FRANKFURTER_LATEST_URL = "https://api.frankfurter.app/latest"
BASE_CURRENCY = "CNY"


def infer_market(symbol: str) -> str | None:
    symbol = str(symbol).strip()
    if re.fullmatch(r"\d{6}", symbol):
        return "CN"
    if re.fullmatch(r"\d{5}", symbol):
        return "HK"
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9.-]{0,14}", symbol):
        return "US"
    return None


def market_currency(market: str) -> str:
    market = str(market).upper().strip()
    currencies = {"CN": "CNY", "HK": "HKD", "US": "USD"}
    if market not in currencies:
        raise ValueError(f"unsupported market: {market}")
    return currencies[market]


def resolve_eastmoney_secid(symbol: str, market: str) -> str:
    symbol = str(symbol).strip().upper()
    market = str(market).upper().strip()
    if market == "CN":
        if not re.fullmatch(r"\d{6}", symbol):
            raise ValueError(f"CN symbol must be 6 digits: {symbol}")
        prefix = "1" if symbol.startswith("6") else "0"
        return f"{prefix}.{symbol}"
    if market == "HK":
        if not re.fullmatch(r"\d{5}", symbol):
            raise ValueError(f"HK symbol must be 5 digits: {symbol}")
        return f"116.{symbol}"
    if market == "US":
        if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,14}", symbol):
            raise ValueError(f"US symbol must be a ticker: {symbol}")
        return f"105.{symbol}"
    raise ValueError(f"unsupported market: {market}")


def fetch_quote(symbol: str, market: str | None = None) -> dict:
    market = str(market or infer_market(symbol) or "").upper().strip()
    if not market:
        raise ValueError(f"cannot infer market for symbol: {symbol}")

    secid = resolve_eastmoney_secid(symbol, market)
    params = {
        "secid": secid,
        "fields": "f43,f57,f58,f59,f107,f152",
    }
    source_url = f"{EASTMONEY_QUOTE_URL}?{urlencode(params)}"
    request = Request(source_url, headers={"User-Agent": "Mozilla/5.0 portfolio-stock-exposure skill"})
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    quote = parse_eastmoney_quote(
        payload,
        requested_symbol=symbol,
        requested_market=market,
        source_url=source_url,
    )
    quote["quote_checked_at"] = datetime.now(timezone.utc).isoformat()
    return quote


def parse_eastmoney_quote(
    payload,
    *,
    requested_symbol: str,
    requested_market: str,
    source_url: str,
) -> dict:
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict) or payload.get("rc") != 0:
        raise ValueError("eastmoney quote response is not successful")

    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("eastmoney quote response missing data")

    raw_price = data.get("f43")
    scale = data.get("f59", data.get("f152"))
    if raw_price in (None, "-", "") or scale in (None, "-", ""):
        raise ValueError("eastmoney quote response missing price or scale")

    price = _decimal(raw_price, "f43") / (Decimal(10) ** int(scale))
    if price <= 0:
        raise ValueError("eastmoney quote price must be positive")

    market = str(requested_market).upper().strip()
    symbol = str(data.get("f57") or requested_symbol).strip().upper()
    return {
        "symbol": symbol,
        "name": str(data.get("f58") or symbol).strip(),
        "market": market,
        "currency": market_currency(market),
        "current_price": _float(price),
        "quote_source": "东方财富",
        "quote_source_url": source_url,
        "quote_raw_price": _float(_decimal(raw_price, "f43")),
        "quote_price_scale": int(scale),
    }


def fetch_fx_rate_to_cny(currency: str) -> dict:
    currency = str(currency).upper().strip()
    if currency == BASE_CURRENCY:
        return {
            "currency": currency,
            "target_currency": BASE_CURRENCY,
            "fx_rate_to_cny": 1.0,
            "fx_date": datetime.now(timezone.utc).date().isoformat(),
            "fx_source": "none",
            "fx_source_url": None,
        }

    params = {"from": currency, "to": BASE_CURRENCY}
    source_url = f"{FRANKFURTER_LATEST_URL}?{urlencode(params)}"
    request = Request(source_url, headers={"User-Agent": "Mozilla/5.0 portfolio-stock-exposure skill"})
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    return parse_frankfurter_rate(payload, currency, source_url=source_url)


def parse_frankfurter_rate(payload, currency: str, *, source_url: str) -> dict:
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict):
        raise ValueError("frankfurter response must be an object")

    currency = str(currency).upper().strip()
    rates = payload.get("rates")
    if not isinstance(rates, dict) or BASE_CURRENCY not in rates:
        raise ValueError(f"frankfurter response missing {BASE_CURRENCY} rate")

    rate = _decimal(rates[BASE_CURRENCY], "fx_rate_to_cny")
    if rate <= 0:
        raise ValueError("fx_rate_to_cny must be positive")

    return {
        "currency": currency,
        "target_currency": BASE_CURRENCY,
        "fx_rate_to_cny": _float(rate),
        "fx_date": str(payload.get("date") or ""),
        "fx_source": "Frankfurter",
        "fx_source_url": source_url,
    }


def _decimal(value, field_name: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if not result.is_finite():
        raise ValueError(f"{field_name} must be finite")
    return result


def _float(value: Decimal) -> float:
    return float(value)
