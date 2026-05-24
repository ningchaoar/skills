from __future__ import annotations

import re
from collections import defaultdict
from copy import deepcopy
from decimal import Decimal, ROUND_FLOOR, InvalidOperation


UNKNOWN_FUND_EXPOSURE = "UNKNOWN_FUND_EXPOSURE"


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


def normalize_positions(positions: list[dict]) -> list[dict]:
    """Validate and normalize raw fund/stock positions.

    The calculation uses market value as the default exposure base. Cost fields
    are preserved for reporting but are not used to compute exposure weights.
    """
    if not isinstance(positions, list):
        raise ValueError("positions must be a list")

    normalized = []
    for idx, raw_position in enumerate(positions):
        if not isinstance(raw_position, dict):
            raise ValueError(f"positions[{idx}] must be an object")

        position = deepcopy(raw_position)
        instrument_type = str(position.get("instrument_type", "")).lower().strip()
        if instrument_type not in {"stock", "fund"}:
            raise ValueError(f"positions[{idx}].instrument_type must be stock or fund")

        symbol = str(position.get("symbol", "")).strip()
        name = str(position.get("name", "")).strip()
        if not symbol and not name:
            raise ValueError(f"positions[{idx}] must include symbol or name")

        market_value = position.get("market_value")
        if market_value is None:
            quantity = position.get("quantity")
            current_price = position.get("current_price")
            if quantity is None or current_price is None:
                raise ValueError(
                    f"positions[{idx}] must include market_value or quantity + current_price"
                )
            market_value_decimal = _decimal(quantity, f"positions[{idx}].quantity") * _decimal(
                current_price, f"positions[{idx}].current_price"
            )
        else:
            market_value_decimal = _decimal(market_value, f"positions[{idx}].market_value")

        if market_value_decimal < 0:
            raise ValueError(f"positions[{idx}].market_value must be non-negative")

        position["instrument_type"] = instrument_type
        position["symbol"] = symbol or name
        position["name"] = name or symbol
        position["market_value"] = _float(market_value_decimal)
        normalized.append(position)

    return normalized


def compute_stock_exposure(positions: list[dict], fund_components: dict) -> dict:
    """Expand fund holdings and return stock-level exposure by market value."""
    normalized_positions = normalize_positions(positions)
    total_market_value = sum(_decimal(item["market_value"], "market_value") for item in normalized_positions)
    exposures = defaultdict(lambda: {"symbol": "", "name": "", "market_value": Decimal("0"), "sources": []})

    for position in normalized_positions:
        value = _decimal(position["market_value"], "market_value")
        if value == 0:
            continue

        if position["instrument_type"] == "stock":
            _add_exposure(
                exposures,
                symbol=position["symbol"],
                name=position["name"],
                market_value=value,
                source={
                    "type": "direct_stock",
                    "symbol": position["symbol"],
                    "name": position["name"],
                    "market": position.get("market") or _infer_market(position["symbol"]),
                    "market_value": _float(value),
                },
            )
            continue

        fund_symbol = position["symbol"]
        holding = fund_components.get(fund_symbol)
        components = holding.get("components", []) if isinstance(holding, dict) else []
        if not components:
            _add_exposure(
                exposures,
                symbol=UNKNOWN_FUND_EXPOSURE,
                name="Unknown fund exposure",
                market_value=value,
                source={
                    "type": "unknown_fund",
                    "fund_symbol": fund_symbol,
                    "fund_name": position["name"],
                    "market_value": _float(value),
                },
            )
            continue

        used_weight = Decimal("0")
        for component in components:
            weight = _decimal(component.get("weight", 0), "component.weight")
            if weight > 1:
                raise ValueError("component.weight must be between 0 and 1")
            if weight <= 0:
                continue
            used_weight += weight
            if used_weight > Decimal("1.000001"):
                raise ValueError("fund component weights must not sum above 1")
            component_value = value * weight
            _add_exposure(
                exposures,
                symbol=str(component.get("symbol", "")).strip() or str(component.get("name", "")).strip(),
                name=str(component.get("name", "")).strip() or str(component.get("symbol", "")).strip(),
                market_value=component_value,
                source={
                    "type": "fund_component",
                    "fund_symbol": fund_symbol,
                    "fund_name": position["name"],
                    "market": component.get("market") or _infer_market(
                        str(component.get("symbol", "")).strip()
                    ),
                    "component_weight": _float(weight),
                    "source": holding.get("source"),
                    "disclosure_date": holding.get("disclosure_date"),
                },
            )

        residual = Decimal("1") - used_weight
        if residual > Decimal("0.000001"):
            _add_exposure(
                exposures,
                symbol=f"UNMAPPED_{fund_symbol}",
                name=f"Unmapped portion of {position['name']}",
                market_value=value * residual,
                source={
                    "type": "unmapped_fund_residual",
                    "fund_symbol": fund_symbol,
                    "fund_name": position["name"],
                    "component_weight": _float(residual),
                    "source": holding.get("source"),
                    "disclosure_date": holding.get("disclosure_date"),
                },
            )

    exposure_items = []
    for item in exposures.values():
        market_value = item["market_value"]
        weight = market_value / total_market_value if total_market_value else Decimal("0")
        exposure_items.append(
            {
                "symbol": item["symbol"],
                "name": item["name"],
                "market": _merged_market(item["sources"]),
                "market_value": _float(market_value),
                "weight": _float(weight),
                "sources": item["sources"],
            }
        )

    exposure_items.sort(key=lambda item: item["market_value"], reverse=True)
    return {
        "total_market_value": _float(total_market_value),
        "exposures": exposure_items,
    }


def _add_exposure(exposures, *, symbol: str, name: str, market_value: Decimal, source: dict) -> None:
    if not symbol:
        raise ValueError("component symbol or name is required")
    item = exposures[symbol]
    item["symbol"] = symbol
    item["name"] = item["name"] or name or symbol
    item["market_value"] += market_value
    item["sources"].append(source)


def _merged_market(sources: list[dict]) -> str | None:
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


def _infer_market(symbol: str) -> str | None:
    symbol = str(symbol).strip()
    if not symbol:
        return None
    if len(symbol) == 6 and symbol.isdigit():
        return "CN"
    if len(symbol) == 5 and symbol.isdigit():
        return "HK"
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9.-]{0,14}", symbol):
        return "US"
    return None


def compute_direct_stock_rebalance(
    exposure: dict,
    *,
    target_symbol: str,
    target_weight,
    current_price,
    lot_size: int = 100,
    current_direct_market_value=None,
) -> dict:
    """Compute a direct buy/sell plan using external cash in or cash out.

    For buys, only the target stock and total portfolio value increase. For
    sells, only the target stock and total portfolio value decrease.
    """
    target_weight = _decimal(target_weight, "target_weight")
    current_price = _decimal(current_price, "current_price")
    total_value = _decimal(exposure.get("total_market_value", 0), "total_market_value")

    if target_weight < 0 or target_weight >= 1:
        raise ValueError("target_weight must be >= 0 and < 1")
    if current_price <= 0:
        raise ValueError("current_price must be positive")
    if total_value <= 0:
        raise ValueError("total_market_value must be positive")
    if lot_size <= 0:
        raise ValueError("lot_size must be positive")
    if current_direct_market_value is not None:
        current_direct_market_value = _decimal(
            current_direct_market_value, "current_direct_market_value"
        )
        if current_direct_market_value < 0:
            raise ValueError("current_direct_market_value must be non-negative")

    current_target_value = Decimal("0")
    target_name = target_symbol
    for item in exposure.get("exposures", []):
        if item.get("symbol") == target_symbol:
            current_target_value = _decimal(item.get("market_value", 0), "target market_value")
            target_name = item.get("name") or target_symbol
            break

    desired_delta = target_weight * total_value - current_target_value
    denominator = Decimal("1") - target_weight
    theoretical_trade_amount = abs(desired_delta) / denominator
    theoretical_shares = theoretical_trade_amount / current_price
    rounded_lots = (theoretical_shares / Decimal(lot_size)).to_integral_value(rounding=ROUND_FLOOR)
    shares = int(rounded_lots * Decimal(lot_size))
    trade_amount = current_price * Decimal(shares)

    capped_by_direct_holding = False
    reason = None
    if desired_delta > 0:
        action = "buy" if shares else "hold"
        final_total = total_value + trade_amount
        final_target_value = current_target_value + trade_amount
    elif desired_delta < 0:
        action = "sell" if shares else "hold"
        max_sell_value = (
            current_target_value
            if current_direct_market_value is None
            else current_direct_market_value
        )
        max_sellable_shares = int(
            (max_sell_value / current_price / Decimal(lot_size)).to_integral_value(
                rounding=ROUND_FLOOR
            )
            * Decimal(lot_size)
        )
        if shares > max_sellable_shares:
            shares = max_sellable_shares
            trade_amount = current_price * Decimal(shares)
            capped_by_direct_holding = True
        if shares == 0:
            action = "not_viable"
            reason = "no direct stock shares are available to sell after lot rounding"
        final_total = total_value - trade_amount
        final_target_value = current_target_value - trade_amount
    else:
        action = "hold"
        shares = 0
        trade_amount = Decimal("0")
        final_total = total_value
        final_target_value = current_target_value

    final_weight = final_target_value / final_total if final_total else Decimal("0")
    return {
        "target_symbol": target_symbol,
        "target_name": target_name,
        "action": action,
        "shares": shares,
        "trade_amount": _float(trade_amount),
        "current_total_market_value": _float(total_value),
        "current_target_market_value": _float(current_target_value),
        "current_target_weight": _float(current_target_value / total_value),
        "target_weight": _float(target_weight),
        "theoretical_trade_amount": _float(theoretical_trade_amount),
        "final_total_market_value": _float(final_total),
        "final_target_market_value": _float(final_target_value),
        "final_target_weight": _float(final_weight),
        "capped_by_direct_holding": capped_by_direct_holding,
        "reason": reason,
        "rounding": {
            "lot_size": lot_size,
            "current_price": _float(current_price),
            "policy": "floor to avoid crossing the target by default",
        },
    }


def compute_instrument_rebalance(
    exposure: dict,
    *,
    target_symbol: str,
    target_weight,
    instrument_symbol: str,
    instrument_name: str,
    instrument_target_weight,
    current_price,
    lot_size: int = 100,
    current_instrument_market_value=None,
) -> dict:
    """Compute a one-instrument rebalance path.

    Use this for a fund when the target stock is one component of the fund.
    instrument_target_weight is the target stock's weight inside that fund.
    """
    target_weight = _decimal(target_weight, "target_weight")
    instrument_target_weight = _decimal(instrument_target_weight, "instrument_target_weight")
    current_price = _decimal(current_price, "current_price")
    total_value = _decimal(exposure.get("total_market_value", 0), "total_market_value")

    if target_weight < 0 or target_weight >= 1:
        raise ValueError("target_weight must be >= 0 and < 1")
    if instrument_target_weight < 0 or instrument_target_weight > 1:
        raise ValueError("instrument_target_weight must be between 0 and 1")
    if current_price <= 0:
        raise ValueError("current_price must be positive")
    if total_value <= 0:
        raise ValueError("total_market_value must be positive")
    if lot_size <= 0:
        raise ValueError("lot_size must be positive")

    current_target_value = Decimal("0")
    target_name = target_symbol
    for item in exposure.get("exposures", []):
        if item.get("symbol") == target_symbol:
            current_target_value = _decimal(item.get("market_value", 0), "target market_value")
            target_name = item.get("name") or target_symbol
            break

    denominator = instrument_target_weight - target_weight
    if denominator == 0:
        return _not_viable_result(
            target_symbol,
            target_name,
            instrument_symbol,
            instrument_name,
            "instrument target weight equals requested portfolio target weight",
        )

    candidates = []
    buy_amount = (target_weight * total_value - current_target_value) / denominator
    if buy_amount > 0:
        units = _rounded_units(buy_amount, current_price, lot_size)
        trade_amount = current_price * Decimal(units)
        candidates.append(
            _instrument_result(
                action="buy",
                target_symbol=target_symbol,
                target_name=target_name,
                instrument_symbol=instrument_symbol,
                instrument_name=instrument_name,
                units=units,
                trade_amount=trade_amount,
                theoretical_trade_amount=buy_amount,
                total_value=total_value,
                target_value=current_target_value,
                target_weight=target_weight,
                instrument_target_weight=instrument_target_weight,
                current_price=current_price,
                lot_size=lot_size,
            )
        )

    sell_amount = (current_target_value - target_weight * total_value) / denominator
    if sell_amount > 0 and current_instrument_market_value is not None:
        max_sell_value = _decimal(current_instrument_market_value, "current_instrument_market_value")
        max_units = _rounded_units(max_sell_value, current_price, lot_size)
        units = min(_rounded_units(sell_amount, current_price, lot_size), max_units)
        trade_amount = current_price * Decimal(units)
        candidates.append(
            _instrument_result(
                action="sell",
                target_symbol=target_symbol,
                target_name=target_name,
                instrument_symbol=instrument_symbol,
                instrument_name=instrument_name,
                units=units,
                trade_amount=trade_amount,
                theoretical_trade_amount=sell_amount,
                total_value=total_value,
                target_value=current_target_value,
                target_weight=target_weight,
                instrument_target_weight=instrument_target_weight,
                current_price=current_price,
                lot_size=lot_size,
            )
        )

    candidates = [candidate for candidate in candidates if candidate["units"] > 0]
    if not candidates:
        return _not_viable_result(
            target_symbol,
            target_name,
            instrument_symbol,
            instrument_name,
            "no trade reaches the target after lot rounding",
        )

    return min(candidates, key=lambda item: abs(item["final_target_weight"] - item["target_weight"]))


def _rounded_units(theoretical_amount: Decimal, current_price: Decimal, lot_size: int) -> int:
    theoretical_units = theoretical_amount / current_price
    rounded_lots = (theoretical_units / Decimal(lot_size)).to_integral_value(rounding=ROUND_FLOOR)
    return int(rounded_lots * Decimal(lot_size))


def _instrument_result(
    *,
    action: str,
    target_symbol: str,
    target_name: str,
    instrument_symbol: str,
    instrument_name: str,
    units: int,
    trade_amount: Decimal,
    theoretical_trade_amount: Decimal,
    total_value: Decimal,
    target_value: Decimal,
    target_weight: Decimal,
    instrument_target_weight: Decimal,
    current_price: Decimal,
    lot_size: int,
) -> dict:
    if action == "buy":
        final_total = total_value + trade_amount
        final_target_value = target_value + instrument_target_weight * trade_amount
    elif action == "sell":
        final_total = total_value - trade_amount
        final_target_value = target_value - instrument_target_weight * trade_amount
    else:
        raise ValueError("action must be buy or sell")

    final_weight = final_target_value / final_total if final_total else Decimal("0")
    return {
        "target_symbol": target_symbol,
        "target_name": target_name,
        "instrument_symbol": instrument_symbol,
        "instrument_name": instrument_name,
        "action": action,
        "units": units,
        "trade_amount": _float(trade_amount),
        "current_total_market_value": _float(total_value),
        "current_target_market_value": _float(target_value),
        "current_target_weight": _float(target_value / total_value),
        "instrument_target_weight": _float(instrument_target_weight),
        "target_weight": _float(target_weight),
        "theoretical_trade_amount": _float(theoretical_trade_amount),
        "final_total_market_value": _float(final_total),
        "final_target_market_value": _float(final_target_value),
        "final_target_weight": _float(final_weight),
        "rounding": {
            "lot_size": lot_size,
            "current_price": _float(current_price),
            "policy": "floor to avoid crossing the target by default",
        },
    }


def _not_viable_result(
    target_symbol: str,
    target_name: str,
    instrument_symbol: str,
    instrument_name: str,
    reason: str,
) -> dict:
    return {
        "target_symbol": target_symbol,
        "target_name": target_name,
        "instrument_symbol": instrument_symbol,
        "instrument_name": instrument_name,
        "action": "not_viable",
        "reason": reason,
    }
