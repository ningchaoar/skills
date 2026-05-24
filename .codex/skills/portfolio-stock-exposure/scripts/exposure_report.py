from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from portfolio_math import UNKNOWN_FUND_EXPOSURE, compute_stock_exposure
from query_state import read_latest_query


def compute_exposure_from_query(query: dict) -> dict:
    positions = query.get("current_positions") or query.get("positions")
    if not positions:
        raise ValueError("query file must include current_positions")
    fund_components = query.get("fund_components", {})
    if not isinstance(fund_components, dict):
        raise ValueError("fund_components must be an object")
    return compute_stock_exposure(positions, fund_components)


def format_exposure_markdown(exposure: dict) -> str:
    total_market_value = float(exposure.get("total_market_value", 0))
    lines = [
        f"总市值：{total_market_value:.2f}",
        "",
        "| 代码 | 名称 | 市场 | 股票维度市值 | 占比 | 来源 | 披露日期 |",
        "|---|---|---|---:|---:|---|---|",
    ]
    unknown_rows = []

    for item in exposure.get("exposures", []):
        symbol = str(item.get("symbol", ""))
        name = str(item.get("name", ""))
        market_value = float(item.get("market_value", 0))
        weight = float(item.get("weight", 0))
        sources = item.get("sources", [])
        market = item.get("market") or _market_from_sources(sources)
        source_types = {source.get("type") for source in sources if isinstance(source, dict)}

        if _is_unknown_or_unmapped(symbol, source_types):
            unknown_rows.append(
                {
                    "symbol": symbol,
                    "market_value": market_value,
                    "weight": weight,
                    "reason": _unknown_reason(sources),
                }
            )
            continue

        lines.append(
            "| {symbol} | {name} | {market} | {market_value:.2f} | {weight:.2%} | {source} | {dates} |".format(
                symbol=symbol,
                name=name,
                market=market or "-",
                market_value=market_value,
                weight=weight,
                source=_source_label(source_types),
                dates=_disclosure_dates(sources),
            )
        )

    if unknown_rows:
        lines.extend(
            [
                "",
                "未知/未映射敞口：",
                "| 标识 | 市值 | 占比 | 原因 |",
                "|---|---:|---:|---|",
            ]
        )
        for row in unknown_rows:
            lines.append(
                "| {symbol} | {market_value:.2f} | {weight:.2%} | {reason} |".format(
                    symbol=row["symbol"],
                    market_value=row["market_value"],
                    weight=row["weight"],
                    reason=row["reason"],
                )
            )

    return "\n".join(lines)


def _is_unknown_or_unmapped(symbol: str, source_types: set) -> bool:
    return (
        symbol == UNKNOWN_FUND_EXPOSURE
        or symbol.startswith("UNMAPPED_")
        or "unknown_fund" in source_types
        or "unmapped_fund_residual" in source_types
    )


def _source_label(source_types: set) -> str:
    has_direct = "direct_stock" in source_types
    has_fund = "fund_component" in source_types
    if has_direct and has_fund:
        return "直接持股 + 基金穿透"
    if has_direct:
        return "直接持股"
    if has_fund:
        return "基金穿透"
    return " + ".join(sorted(str(item) for item in source_types if item)) or "-"


def _market_from_sources(sources: list[dict]) -> str | None:
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


def _disclosure_dates(sources: list[dict]) -> str:
    dates = {
        str(source.get("disclosure_date"))
        for source in sources
        if isinstance(source, dict) and source.get("disclosure_date")
    }
    return ", ".join(sorted(dates)) if dates else "-"


def _unknown_reason(sources: list[dict]) -> str:
    for source in sources:
        if not isinstance(source, dict):
            continue
        source_type = source.get("type")
        fund_symbol = source.get("fund_symbol")
        if source_type == "unknown_fund":
            return f"未取得 {fund_symbol} 的基金成分股" if fund_symbol else "未取得基金成分股"
        if source_type == "unmapped_fund_residual":
            return f"{fund_symbol} 成分股未完全披露" if fund_symbol else "基金成分股未完全披露"
    return "无法穿透"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Render stock-level exposure from the single latest query file.")
    parser.add_argument("--query-file", type=Path, help="Path to latest_query.json. Defaults to skill tmp/latest_query.json.")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args(argv)

    try:
        query = read_latest_query(args.query_file)
        exposure = compute_exposure_from_query(query)
    except Exception as exc:
        print(f"exposure report failed: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        print(json.dumps(exposure, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(format_exposure_markdown(exposure))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
