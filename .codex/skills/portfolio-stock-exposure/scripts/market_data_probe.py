from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from market_data import fetch_fx_rate_to_cny, fetch_quote


DEFAULT_QUOTES = ["CN:300750", "HK:00700", "US:PDD"]
DEFAULT_CURRENCIES = ["USD", "HKD"]


def probe_market_data(
    *,
    quote_specs: list[str],
    currencies: list[str],
    quote_fetcher=fetch_quote,
    fx_fetcher=fetch_fx_rate_to_cny,
) -> dict:
    quotes = []
    fx_rates = []
    errors = []

    for spec in quote_specs:
        try:
            market, symbol = _parse_quote_spec(spec)
            quotes.append(quote_fetcher(symbol, market))
        except Exception as exc:
            errors.append({"type": "quote", "spec": spec, "error": repr(exc)})

    for currency in currencies:
        try:
            fx_rates.append(fx_fetcher(currency))
        except Exception as exc:
            errors.append({"type": "fx", "currency": currency, "error": repr(exc)})

    return {
        "ok": not errors,
        "quotes": quotes,
        "fx_rates": fx_rates,
        "errors": errors,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def _parse_quote_spec(spec: str) -> tuple[str, str]:
    if ":" not in spec:
        raise ValueError(f"quote spec must be MARKET:SYMBOL: {spec}")
    market, symbol = spec.split(":", 1)
    market = market.upper().strip()
    symbol = symbol.strip()
    if not market or not symbol:
        raise ValueError(f"quote spec must be MARKET:SYMBOL: {spec}")
    return market, symbol


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Probe quote and FX data sources used by portfolio-stock-exposure.")
    parser.add_argument("--quotes", nargs="*", default=DEFAULT_QUOTES, help="Quote specs like CN:300750 HK:00700 US:PDD.")
    parser.add_argument("--currencies", nargs="*", default=DEFAULT_CURRENCIES, help="Currencies to convert to CNY.")
    args = parser.parse_args(argv)

    report = probe_market_data(quote_specs=args.quotes, currencies=args.currencies)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
