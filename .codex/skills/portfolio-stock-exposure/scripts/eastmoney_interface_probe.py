from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timezone

from fund_components import fetch_eastmoney_holdings


def assess_stability(results: list[dict], *, min_components: int = 1, compare_top_n: int = 5) -> dict:
    """Assess whether repeated parsed Eastmoney responses look structurally stable."""
    if not results:
        return {"stable": False, "reason": "no results"}

    first = results[0]
    first_components = first.get("components") or []
    if len(first_components) < min_components:
        return {
            "stable": False,
            "reason": f"too few components: {len(first_components)} < {min_components}",
            "component_count": len(first_components),
            "disclosure_date": first.get("disclosure_date"),
        }

    missing_fields = _missing_required_fields(first_components)
    if missing_fields:
        return {
            "stable": False,
            "reason": f"missing required fields: {', '.join(missing_fields)}",
            "component_count": len(first_components),
            "disclosure_date": first.get("disclosure_date"),
        }

    first_date = first.get("disclosure_date")
    first_symbols = _top_symbols(first_components, compare_top_n)
    for idx, result in enumerate(results[1:], start=2):
        components = result.get("components") or []
        if result.get("disclosure_date") != first_date:
            return {
                "stable": False,
                "reason": f"disclosure date changed on attempt {idx}: {first_date} -> {result.get('disclosure_date')}",
                "component_count": len(components),
                "disclosure_date": result.get("disclosure_date"),
            }
        if _top_symbols(components, compare_top_n) != first_symbols:
            return {
                "stable": False,
                "reason": f"top components changed on attempt {idx}",
                "component_count": len(components),
                "disclosure_date": result.get("disclosure_date"),
            }

    return {
        "stable": True,
        "reason": "ok",
        "component_count": len(first_components),
        "disclosure_date": first_date,
        "top_symbols": first_symbols,
    }


def probe_fund(
    fund_code: str,
    *,
    year: str | int | None = None,
    attempts: int = 3,
    delay_seconds: float = 1.0,
    min_components: int = 1,
    compare_top_n: int = 5,
) -> dict:
    """Run live repeated checks against the Eastmoney/Tiantian Fund holdings endpoint."""
    query_year = str(year or date.today().year)
    results = []
    errors = []
    timings = []

    for attempt in range(1, attempts + 1):
        started = time.perf_counter()
        try:
            result = fetch_eastmoney_holdings(fund_code, query_year)
            timings.append(round(time.perf_counter() - started, 3))
            results.append(result)
        except Exception as exc:
            timings.append(round(time.perf_counter() - started, 3))
            errors.append({"attempt": attempt, "error": repr(exc)})
        if attempt < attempts and delay_seconds > 0:
            time.sleep(delay_seconds)

    stability = assess_stability(results, min_components=min_components, compare_top_n=compare_top_n)
    stable = not errors and stability["stable"]
    return {
        "fund_code": fund_code,
        "year": query_year,
        "attempts": attempts,
        "successful_attempts": len(results),
        "stable": stable,
        "reason": "ok" if stable else _failure_reason(errors, stability),
        "stability": stability,
        "timings_seconds": timings,
        "errors": errors,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def _missing_required_fields(components: list[dict]) -> list[str]:
    required_fields = ["symbol", "name", "weight", "raw_weight_percent"]
    missing = set()
    for component in components:
        for field in required_fields:
            if component.get(field) in (None, ""):
                missing.add(field)
    return sorted(missing)


def _top_symbols(components: list[dict], count: int) -> list[str]:
    return [str(item.get("symbol", "")) for item in components[:count]]


def _failure_reason(errors: list[dict], stability: dict) -> str:
    if errors:
        return f"{len(errors)} request errors"
    return stability.get("reason", "unstable")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Probe Eastmoney/Tiantian Fund holdings endpoint stability."
    )
    parser.add_argument("--fund-codes", nargs="+", default=["159836", "515050"])
    parser.add_argument("--year", default=str(date.today().year))
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    parser.add_argument("--min-components", type=int, default=1)
    parser.add_argument("--compare-top-n", type=int, default=5)
    args = parser.parse_args(argv)

    reports = [
        probe_fund(
            fund_code,
            year=args.year,
            attempts=args.attempts,
            delay_seconds=args.delay_seconds,
            min_components=args.min_components,
            compare_top_n=args.compare_top_n,
        )
        for fund_code in args.fund_codes
    ]
    output = {
        "stable": all(report["stable"] for report in reports),
        "reports": reports,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if output["stable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
