from __future__ import annotations

import argparse
import sys
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from market_data import (
    BASE_CURRENCY,
    fetch_fx_rate_to_cny,
    fetch_quote,
    infer_market,
    market_currency,
)
from query_state import read_latest_query, write_latest_query


def enrich_position_values(
    query: dict,
    *,
    quote_fetcher=fetch_quote,
    fx_fetcher=fetch_fx_rate_to_cny,
) -> dict:
    if not isinstance(query, dict):
        raise ValueError("query must be an object")

    positions = query.get("current_positions")
    if not isinstance(positions, list):
        raise ValueError("query file must include current_positions")

    enriched = deepcopy(query)
    enriched["current_positions"] = [
        _enrich_position(position, idx, quote_fetcher=quote_fetcher, fx_fetcher=fx_fetcher)
        for idx, position in enumerate(positions)
    ]
    enriched["position_value_query"] = {
        "base_currency": BASE_CURRENCY,
        "queried_at": datetime.now(timezone.utc).isoformat(),
    }
    return enriched


def update_latest_query_with_position_values(
    path=None,
    *,
    quote_fetcher=fetch_quote,
    fx_fetcher=fetch_fx_rate_to_cny,
) -> dict:
    query = read_latest_query(path)
    enriched = enrich_position_values(query, quote_fetcher=quote_fetcher, fx_fetcher=fx_fetcher)
    write_latest_query(enriched, path)
    return enriched


def _enrich_position(position: dict, idx: int, *, quote_fetcher, fx_fetcher) -> dict:
    if not isinstance(position, dict):
        raise ValueError(f"positions[{idx}] must be an object")

    enriched = deepcopy(position)
    instrument_type = str(enriched.get("instrument_type", "")).lower().strip()
    if instrument_type != "stock":
        return enriched

    symbol = str(enriched.get("symbol", "")).strip()
    if not symbol:
        raise ValueError(f"positions[{idx}] must include symbol")

    market = str(enriched.get("market") or infer_market(symbol) or "").upper().strip()
    if not market:
        raise ValueError(f"positions[{idx}] market cannot be inferred for symbol {symbol}")
    enriched["market"] = market

    if enriched.get("market_value") is not None:
        return enriched

    quantity = enriched.get("quantity")
    if quantity is None:
        raise ValueError(f"positions[{idx}] must include market_value or quantity")

    quote = None
    current_price = enriched.get("current_price")
    currency = str(enriched.get("currency") or "").upper().strip()
    if current_price is None:
        quote = quote_fetcher(symbol, market)
        current_price = quote["current_price"]
        currency = str(quote.get("currency") or market_currency(market)).upper().strip()
        enriched["current_price"] = current_price
        enriched["currency"] = currency
        enriched["name"] = enriched.get("name") or quote.get("name") or symbol
        for field in ("quote_source", "quote_source_url", "quote_checked_at"):
            if quote.get(field) is not None:
                enriched[field] = quote[field]
    else:
        currency = currency or market_currency(market)
        enriched["currency"] = currency

    local_market_value = _decimal(quantity, f"positions[{idx}].quantity") * _decimal(
        current_price, f"positions[{idx}].current_price"
    )
    if local_market_value < 0:
        raise ValueError(f"positions[{idx}].local_market_value must be non-negative")

    fx = fx_fetcher(currency)
    fx_rate = _decimal(fx.get("fx_rate_to_cny"), "fx_rate_to_cny")
    enriched["local_market_value"] = _float(local_market_value)
    enriched["fx_rate_to_cny"] = _float(fx_rate)
    enriched["market_value"] = _float(local_market_value * fx_rate)
    for field in ("fx_source", "fx_source_url", "fx_date"):
        if fx.get(field) is not None:
            enriched[field] = fx[field]

    return enriched


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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fill missing direct stock market values into latest_query.json.")
    parser.add_argument("--query-file", type=Path, help="Path to latest_query.json. Defaults to skill tmp/latest_query.json.")
    args = parser.parse_args(argv)

    try:
        payload = update_latest_query_with_position_values(args.query_file)
    except Exception as exc:
        print(f"position value query failed: {exc}", file=sys.stderr)
        return 1

    print(write_latest_query(payload, args.query_file))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
