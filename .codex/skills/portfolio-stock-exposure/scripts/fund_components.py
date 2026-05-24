from __future__ import annotations

import argparse
import html
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from query_state import read_latest_query, resolve_query_path, write_latest_query
from script_utils import infer_market


EASTMONEY_ARCHIVES_URL = "https://fundf10.eastmoney.com/FundArchivesDatas.aspx"


def fetch_fund_components(fund_codes: list[str], year: str | int | None = None) -> dict:
    """Fetch fund stock holdings from Eastmoney/Tiantian Fund public pages."""
    components = {}
    query_year = str(year or date.today().year)
    for fund_code in fund_codes:
        fund_code = str(fund_code).strip()
        if not fund_code:
            continue
        components[fund_code] = fetch_eastmoney_holdings(fund_code, query_year)
    return components


def fetch_eastmoney_holdings(fund_code: str, year: str) -> dict:
    params = {
        "type": "jjcc",
        "code": fund_code,
        "topline": "100",
        "year": str(year),
        "month": "",
    }
    source_url = f"{EASTMONEY_ARCHIVES_URL}?{urlencode(params)}"
    request = Request(
        source_url,
        headers={
            "User-Agent": "Mozilla/5.0 portfolio-stock-exposure skill",
            "Referer": f"https://fundf10.eastmoney.com/ccmx_{fund_code}.html",
        },
    )
    with urlopen(request, timeout=20) as response:
        raw = response.read()
    text = raw.decode("utf-8", errors="replace")
    return parse_eastmoney_holdings(text, fund_code=fund_code, source_url=source_url)


def parse_eastmoney_holdings(text: str, *, fund_code: str, source_url: str) -> dict:
    """Parse Eastmoney/Tiantian Fund holding rows into compute_stock_exposure format."""
    normalized = _normalize_html_payload(text)
    components = []
    for section in _extract_sections(normalized):
        section_date = _extract_section_disclosure_date(section)
        rows = _extract_table_rows(section)
        for row in rows:
            cells = _extract_cells(row)
            parsed = _parse_holding_cells(cells)
            if parsed is not None:
                parsed["quarter"] = parsed["quarter"] or section_date
                components.append(parsed)

    latest_quarter = _latest_quarter(components)
    if latest_quarter is not None:
        components = [item for item in components if item["quarter"] == latest_quarter]

    return {
        "source": "东方财富-天天基金",
        "source_url": source_url,
        "disclosure_date": latest_quarter,
        "fund_code": fund_code,
        "components": [
            {
                "symbol": item["symbol"],
                "name": item["name"],
                "market": item["market"],
                "weight": item["weight"],
                "raw_weight_percent": item["raw_weight_percent"],
                "quarter": item["quarter"],
                "shares_10k": item["shares_10k"],
                "market_value_10k": item["market_value_10k"],
            }
            for item in components
        ],
    }


def update_latest_query_with_fund_components(path=None, year: str | int | None = None) -> dict:
    query = read_latest_query(path)
    fund_codes = query.get("fund_codes")
    if not fund_codes:
        fund_codes = sorted(
            {
                str(item.get("symbol", "")).strip()
                for item in query.get("current_positions", [])
                if item.get("instrument_type") == "fund" and item.get("symbol")
            }
        )
    if not fund_codes:
        raise ValueError("query file must include fund_codes or fund positions in current_positions")

    query["fund_components"] = fetch_fund_components(fund_codes, year=year)
    query["fund_component_query"] = {
        "provider": "eastmoney_tiantian_fund",
        "queried_at": datetime.now(timezone.utc).isoformat(),
        "year": str(year or date.today().year),
    }
    write_latest_query(query, path)
    return query


def _normalize_html_payload(text: str) -> str:
    text = html.unescape(text)
    text = text.replace(r"\/", "/").replace(r"\"", '"').replace(r"\n", "")
    text = text.replace("\\'", "'")
    return text


def _extract_table_rows(text: str) -> list[str]:
    return re.findall(r"<tr\b[^>]*>.*?</tr>", text, flags=re.IGNORECASE | re.DOTALL)


def _extract_sections(text: str) -> list[str]:
    sections = re.findall(
        r"<h4\b[^>]*>.*?</h4>.*?<table\b[^>]*>.*?</table>",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return sections or [text]


def _extract_section_disclosure_date(section: str) -> str | None:
    date_match = re.search(r"截止至[:：]\s*<[^>]*>\s*(\d{4}-\d{2}-\d{2})\s*</", section)
    if date_match:
        return date_match.group(1)
    quarter_match = re.search(r"(\d{4}\s*年\s*\d+\s*季度)", section)
    if quarter_match:
        return re.sub(r"\s+", "", quarter_match.group(1))
    return None


def _extract_cells(row: str) -> list[str]:
    cells = re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row, flags=re.IGNORECASE | re.DOTALL)
    return [_clean_cell(cell) for cell in cells]


def _clean_cell(cell: str) -> str:
    cell = re.sub(r"<.*?>", "", cell, flags=re.DOTALL)
    cell = html.unescape(cell)
    return re.sub(r"\s+", " ", cell).strip()


def _parse_holding_cells(cells: list[str]) -> dict | None:
    if len(cells) < 4:
        return None

    stock_code_index = _find_stock_code_index(cells)
    if stock_code_index is None or stock_code_index + 2 >= len(cells):
        return None

    symbol = cells[stock_code_index]
    name = cells[stock_code_index + 1]
    percent_index = _find_percent_index(cells, stock_code_index + 2)
    if percent_index is None:
        return None

    percent = _parse_percent(cells[percent_index])
    if percent is None:
        return None

    shares_10k = _parse_float(cells[percent_index + 1]) if percent_index + 1 < len(cells) else None
    market_value_10k = _parse_float(cells[percent_index + 2]) if percent_index + 2 < len(cells) else None
    quarter = cells[percent_index + 3] if percent_index + 3 < len(cells) else None

    return {
        "symbol": symbol,
        "name": name,
        "market": infer_market(symbol),
        "weight": round(percent / 100, 10),
        "raw_weight_percent": percent,
        "quarter": quarter,
        "shares_10k": shares_10k,
        "market_value_10k": market_value_10k,
    }


def _find_stock_code_index(cells: list[str]) -> int | None:
    for idx, cell in enumerate(cells):
        if _is_security_symbol(cell):
            return idx
    return None


def _is_security_symbol(value: str) -> bool:
    value = value.strip()
    if re.fullmatch(r"\d{5,6}", value):
        return True
    return re.fullmatch(r"[A-Za-z][A-Za-z0-9.-]{0,14}", value) is not None


def _find_percent_index(cells: list[str], start_index: int) -> int | None:
    for idx in range(start_index, len(cells)):
        if "%" in cells[idx] and _parse_percent(cells[idx]) is not None:
            return idx
    return None


def _parse_percent(value: str) -> float | None:
    match = re.search(r"[-+]?\d+(?:\.\d+)?", value.replace(",", ""))
    if not match:
        return None
    return float(match.group(0))


def _parse_float(value: str) -> float | None:
    match = re.search(r"[-+]?\d+(?:\.\d+)?", value.replace(",", ""))
    if not match:
        return None
    return float(match.group(0))


def _latest_quarter(components: list[dict]) -> str | None:
    quarters = [item.get("quarter") for item in components if item.get("quarter")]
    if not quarters:
        return None
    return max(quarters, key=_quarter_sort_key)


def _quarter_sort_key(value: str) -> tuple[int, int, str]:
    digits = [int(item) for item in re.findall(r"\d+", value)]
    year = digits[0] if digits else 0
    quarter = digits[1] if len(digits) > 1 else 0
    return year, quarter, value


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fetch fund stock components into the single latest query file.")
    parser.add_argument("--fund-codes", nargs="*", help="Fund codes to query. If omitted, read from latest query file.")
    parser.add_argument("--year", help="Disclosure year to query. Defaults to current year.")
    parser.add_argument("--query-file", type=Path, help="Path to latest_query.json. Defaults to skill tmp/latest_query.json.")
    args = parser.parse_args(argv)

    try:
        if args.fund_codes:
            payload = {
                "fund_codes": args.fund_codes,
                "fund_components": fetch_fund_components(args.fund_codes, year=args.year),
                "fund_component_query": {
                    "provider": "eastmoney_tiantian_fund",
                    "queried_at": datetime.now(timezone.utc).isoformat(),
                    "year": str(args.year or date.today().year),
                },
            }
            write_latest_query(payload, args.query_file)
        else:
            update_latest_query_with_fund_components(args.query_file, year=args.year)
    except Exception as exc:
        print(f"fund component query failed: {exc}", file=sys.stderr)
        return 1

    print(resolve_query_path(args.query_file))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
