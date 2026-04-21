from __future__ import annotations

import json
import math
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bulk_sdk import BulkClient
from bulk_sdk.signer import BulkSigner


def find_oid(value):
    if isinstance(value, dict):
        if "oid" in value:
            return value["oid"]
        for nested in value.values():
            oid = find_oid(nested)
            if oid is not None:
                return oid
    elif isinstance(value, list):
        for nested in value:
            oid = find_oid(nested)
            if oid is not None:
                return oid
    return None


def item_raw(value):
    return getattr(value, "raw", value)


def item_fingerprint(value) -> str:
    return json.dumps(item_raw(value), sort_keys=True, default=str)


def new_items(before, after):
    before_keys = {item_fingerprint(item) for item in before}
    return [item for item in after if item_fingerprint(item) not in before_keys]


def status_names(response) -> list[str]:
    names: list[str] = []
    for status in getattr(response, "statuses", []) or []:
        if isinstance(status, dict) and status:
            names.append(next(iter(status.keys())))
        else:
            names.append(str(status))
    return names


def print_typed_response(label: str, response) -> None:
    print(label)
    print(response)
    print("RESPONSE STATUS NAMES:", status_names(response))
    print("FIRST STATUS:", response.statuses[0] if response.statuses else None)


def get_btc_market(client: BulkClient):
    markets = client.get_markets()
    return next(item for item in markets if item.symbol == "BTC-USD")


def get_safe_btc_size(client: BulkClient, ticker, requested_size: float = 0.001) -> float:
    market = get_btc_market(client)
    raw_min_size = max(
        requested_size,
        market.lotSize,
        market.minNotional / max(ticker.lastPrice, 1.0),
    )
    steps = max(1, math.ceil(raw_min_size / market.lotSize))
    return round(steps * market.lotSize, market.sizePrecision)


def snapshot_account_views(client: BulkClient, user: str) -> dict:
    fills = client.get_fills(user)
    open_orders = client.get_open_orders_typed(user)
    order_history = client.get_order_history(user)
    account = client.get_full_account(user)
    return {
        "fills": fills,
        "open_orders": open_orders,
        "order_history": order_history,
        "account": account,
    }


def print_snapshot_delta(label: str, before: dict, after: dict) -> None:
    new_fills = new_items(before["fills"], after["fills"])
    new_open_orders = new_items(before["open_orders"], after["open_orders"])
    new_order_history = new_items(before["order_history"], after["order_history"])

    print(label)
    print("NEW FILLS COUNT:", len(new_fills))
    print("FIRST NEW FILL:", new_fills[0] if new_fills else None)
    print("NEW OPEN ORDERS COUNT:", len(new_open_orders))
    print("FIRST NEW OPEN ORDER:", new_open_orders[0] if new_open_orders else None)
    print("NEW ORDER HISTORY COUNT:", len(new_order_history))
    print("FIRST NEW ORDER HISTORY:", new_order_history[0] if new_order_history else None)
    print("POSITIONS COUNT:", len(after["account"].positions))
    print("FIRST POSITION:", after["account"].positions[0] if after["account"].positions else None)


def wait_for_account_change(
    client: BulkClient,
    user: str,
    before: dict,
    attempts: int = 5,
    delay: float = 1.0,
) -> dict:
    latest = before
    for _ in range(attempts):
        time.sleep(delay)
        latest = snapshot_account_views(client, user)
        if (
            new_items(before["fills"], latest["fills"])
            or new_items(before["open_orders"], latest["open_orders"])
            or new_items(before["order_history"], latest["order_history"])
        ):
            return latest
    return latest


def wait_for_root_progress_or_completion(
    client: BulkClient,
    user: str,
    baseline: dict,
    root_oid: str | None,
    attempts: int = 30,
    delay: float = 1.0,
) -> dict:
    latest = baseline
    for _ in range(attempts):
        time.sleep(delay)
        latest = snapshot_account_views(client, user)

        if (
            new_items(baseline["fills"], latest["fills"])
            or new_items(baseline["order_history"], latest["order_history"])
        ):
            return latest

        if root_oid is not None:
            still_open = any(getattr(order, "orderId", None) == root_oid for order in latest["open_orders"])
            if not still_open:
                return latest

        if new_items(baseline["open_orders"], latest["open_orders"]):
            return latest

    return latest


def print_btc_relevant_candidates(label: str, before: dict, after: dict) -> tuple[list, list, list]:
    new_fills = [item for item in new_items(before["fills"], after["fills"]) if getattr(item, "symbol", None) == "BTC-USD"]
    new_open_orders = [item for item in new_items(before["open_orders"], after["open_orders"]) if getattr(item, "symbol", None) == "BTC-USD"]
    new_order_history = [item for item in new_items(before["order_history"], after["order_history"]) if getattr(item, "symbol", None) == "BTC-USD"]

    trigger_roots_open = [item for item in new_open_orders if getattr(item, "trigger", None) is not None]
    trigger_roots_history = [item for item in new_order_history if getattr(item, "trigger", None) is not None]
    generic_cancelled = [
        item
        for item in new_order_history
        if "cancel" in str(getattr(item, "status", "")).lower()
        or "cancel" in str(getattr(item, "reason", "")).lower()
    ]

    print(label)
    print("BTC NEW FILLS COUNT:", len(new_fills))
    print("FIRST BTC NEW FILL:", new_fills[0] if new_fills else None)
    print("BTC NEW OPEN ORDERS COUNT:", len(new_open_orders))
    print("FIRST BTC NEW OPEN ORDER:", new_open_orders[0] if new_open_orders else None)
    print("BTC NEW ORDER HISTORY COUNT:", len(new_order_history))
    print("FIRST BTC NEW ORDER HISTORY:", new_order_history[0] if new_order_history else None)
    print("TRIGGER ROOT OPEN ORDER CANDIDATES:", len(trigger_roots_open))
    print("FIRST TRIGGER ROOT OPEN ORDER:", trigger_roots_open[0] if trigger_roots_open else None)
    print("TRIGGER ROOT ORDER HISTORY CANDIDATES:", len(trigger_roots_history))
    print("FIRST TRIGGER ROOT ORDER HISTORY:", trigger_roots_history[0] if trigger_roots_history else None)
    print("GENERIC CANCEL CANDIDATES:", len(generic_cancelled))
    print("FIRST GENERIC CANCEL CANDIDATE:", generic_cancelled[0] if generic_cancelled else None)

    return new_fills, new_open_orders, new_order_history


def run_basic(client: BulkClient, secret_key: str) -> bool:
    user = BulkSigner(secret_key).account

    print("BASIC CONFIRMED PATH:")
    place_response = client.place_limit_order(
        secret_key=secret_key,
        symbol="BTC-USD",
        side="buy",
        price=50000.0,
        size=0.001,
        tif="GTC",
        reduce_only=False,
    )
    print_typed_response("LIMIT PLACE:", place_response)

    oid = find_oid(place_response.statuses)
    if oid is None:
        print("No oid found in place response; skipping remaining basic path.")
        return False

    modify_response = client.modify_order(
        secret_key=secret_key,
        symbol="BTC-USD",
        order_id=oid,
        amount=0.002,
    )
    print_typed_response("MODIFY ORDER:", modify_response)

    cancel_response = client.cancel_order(
        secret_key=secret_key,
        symbol="BTC-USD",
        order_id=oid,
    )
    print_typed_response("CANCEL SINGLE:", cancel_response)

    print("MARKET ORDER TEST:")
    ticker = client.get_ticker("BTC-USD")
    print("TICKER BTC-USD:")
    print(ticker)

    market_size = get_safe_btc_size(client, ticker)
    print("MARKET ORDER SIZE:", market_size)

    market_response = client.place_market_order(
        secret_key=secret_key,
        symbol="BTC-USD",
        side="buy",
        size=market_size,
        reduce_only=False,
    )
    print_typed_response("MARKET ORDER RESPONSE:", market_response)

    account = client.get_full_account(user)
    print("FULL ACCOUNT AFTER MARKET:")
    print(account)
    print("POSITIONS COUNT:", len(account.positions))
    print("FIRST POSITION:", account.positions[0] if account.positions else None)
    return True


def run_conditional_registration(client: BulkClient, secret_key: str) -> None:
    print("CONDITIONAL REGISTRATION PATH:")
    conditional_ticker = client.get_ticker("BTC-USD")
    print("CONDITIONAL TICKER BTC-USD:")
    print(conditional_ticker)

    stop_trigger = round(conditional_ticker.lastPrice * 0.5, 2)
    stop_limit = round(stop_trigger * 0.999, 2)
    tp_trigger = round(conditional_ticker.lastPrice * 1.5, 2)
    tp_limit = round(tp_trigger * 1.001, 2)

    stop_response = client.place_stop_order(
        secret_key=secret_key,
        symbol="BTC-USD",
        direction_above=False,
        size=0.001,
        trigger_price=stop_trigger,
        limit_price=stop_limit,
    )
    print_typed_response("STOP ORDER:", stop_response)

    take_profit_response = client.place_take_profit_order(
        secret_key=secret_key,
        symbol="BTC-USD",
        direction_above=True,
        size=0.001,
        trigger_price=tp_trigger,
        limit_price=tp_limit,
    )
    print_typed_response("TAKE PROFIT ORDER:", take_profit_response)

    conditional_cleanup = client.cancel_all(secret_key=secret_key, symbols=["BTC-USD"])
    print_typed_response("CONDITIONAL CLEANUP CANCEL ALL BTC-USD:", conditional_cleanup)

    range_response = client.place_range_order(
        secret_key=secret_key,
        symbol="BTC-USD",
        direction_above=True,
        size=0.001,
        lower_trigger=round(conditional_ticker.lastPrice * 0.5, 2),
        upper_trigger=round(conditional_ticker.lastPrice * 1.5, 2),
        lower_limit=round(conditional_ticker.lastPrice * 0.5 * 0.999, 2),
        upper_limit=round(conditional_ticker.lastPrice * 1.5 * 1.001, 2),
    )
    print_typed_response("RANGE / OCO ORDER:", range_response)

    range_cleanup = client.cancel_all(secret_key=secret_key, symbols=["BTC-USD"])
    print_typed_response("RANGE CLEANUP CANCEL ALL BTC-USD:", range_cleanup)

    trailing_response = client.place_trailing_stop_order(
        secret_key=secret_key,
        symbol="BTC-USD",
        protected_is_long=True,
        size=0.5,
        trail_bps=100,
        step_bps=10,
        limit_price=None,
    )
    print_typed_response("TRAILING STOP ORDER:", trailing_response)

    trailing_cleanup = client.cancel_all(secret_key=secret_key, symbols=["BTC-USD"])
    print_typed_response("TRAILING CLEANUP CANCEL ALL BTC-USD:", trailing_cleanup)


def run_stop_trigger_verification(client: BulkClient, secret_key: str, user: str) -> None:
    print("STOP TRIGGER VERIFICATION:")
    ticker = client.get_ticker("BTC-USD")
    print("STOP VERIFY TICKER BTC-USD:")
    print(ticker)

    size = get_safe_btc_size(client, ticker)
    before = snapshot_account_views(client, user)
    trigger_price = round(ticker.lastPrice * 1.001, 2)

    response = client.place_stop_order(
        secret_key=secret_key,
        symbol="BTC-USD",
        direction_above=False,
        size=size,
        trigger_price=trigger_price,
        limit_price=None,
    )
    print_typed_response("STOP TRIGGER RESPONSE:", response)

    after = wait_for_account_change(client, user, before, attempts=10, delay=1.0)
    print_snapshot_delta("STOP TRIGGER ACCOUNT DELTA:", before, after)
    _, new_open_orders, _ = print_btc_relevant_candidates("STOP TRIGGER RELEVANT OBJECTS:", before, after)

    if new_open_orders:
        cleanup = client.cancel_all(secret_key=secret_key, symbols=["BTC-USD"])
        print_typed_response("STOP TRIGGER CLEANUP:", cleanup)
    else:
        print("STOP TRIGGER CLEANUP: not needed")


def run_take_profit_trigger_verification(client: BulkClient, secret_key: str, user: str) -> None:
    print("TAKE PROFIT TRIGGER VERIFICATION:")
    ticker = client.get_ticker("BTC-USD")
    print("TAKE PROFIT VERIFY TICKER BTC-USD:")
    print(ticker)

    size = get_safe_btc_size(client, ticker)
    before = snapshot_account_views(client, user)
    trigger_price = round(ticker.lastPrice * 0.999, 2)

    response = client.place_take_profit_order(
        secret_key=secret_key,
        symbol="BTC-USD",
        direction_above=True,
        size=size,
        trigger_price=trigger_price,
        limit_price=None,
    )
    print_typed_response("TAKE PROFIT TRIGGER RESPONSE:", response)

    after = wait_for_account_change(client, user, before, attempts=10, delay=1.0)
    print_snapshot_delta("TAKE PROFIT ACCOUNT DELTA:", before, after)
    _, new_open_orders, _ = print_btc_relevant_candidates("TAKE PROFIT RELEVANT OBJECTS:", before, after)

    if new_open_orders:
        cleanup = client.cancel_all(secret_key=secret_key, symbols=["BTC-USD"])
        print_typed_response("TAKE PROFIT CLEANUP:", cleanup)
    else:
        print("TAKE PROFIT CLEANUP: not needed")


def run_range_trigger_verification(client: BulkClient, secret_key: str, user: str) -> None:
    print("RANGE / OCO TRIGGER VERIFICATION:")
    ticker = client.get_ticker("BTC-USD")
    print("RANGE VERIFY TICKER BTC-USD:")
    print(ticker)

    size = get_safe_btc_size(client, ticker)
    before = snapshot_account_views(client, user)

    response = client.place_range_order(
        secret_key=secret_key,
        symbol="BTC-USD",
        direction_above=True,
        size=size,
        lower_trigger=round(ticker.lastPrice * 0.9, 2),
        upper_trigger=round(ticker.lastPrice * 0.95, 2),
        lower_limit=round(ticker.lastPrice * 0.9 * 0.999, 2),
        upper_limit=round(ticker.lastPrice * 0.95 * 1.001, 2),
    )
    print_typed_response("RANGE / OCO TRIGGER RESPONSE:", response)

    after = wait_for_account_change(client, user, before, attempts=10, delay=1.0)
    print_snapshot_delta("RANGE / OCO ACCOUNT DELTA:", before, after)
    _, new_open_orders, new_order_history = print_btc_relevant_candidates("RANGE / OCO RELEVANT OBJECTS:", before, after)

    exact_sibling_cancelled = [
        item
        for item in new_order_history
        if str(getattr(item, "status", "")) == "siblingCancelled"
        or str(getattr(item, "reason", "")) == "siblingCancelled"
    ]
    generic_cancelled = [
        item
        for item in new_order_history
        if item not in exact_sibling_cancelled
        and (
            "cancel" in str(getattr(item, "status", "")).lower()
            or "cancel" in str(getattr(item, "reason", "")).lower()
        )
    ]
    print("RANGE EXACT SIBLING CANCELLED CANDIDATES:", len(exact_sibling_cancelled))
    print("FIRST RANGE EXACT SIBLING CANCELLED:", exact_sibling_cancelled[0] if exact_sibling_cancelled else None)
    print("RANGE GENERIC CANCELLED CANDIDATES:", len(generic_cancelled))
    print("FIRST RANGE GENERIC CANCELLED:", generic_cancelled[0] if generic_cancelled else None)

    if new_open_orders:
        cleanup = client.cancel_all(secret_key=secret_key, symbols=["BTC-USD"])
        print_typed_response("RANGE / OCO CLEANUP:", cleanup)
    else:
        print("RANGE / OCO CLEANUP: not needed")


def run_trailing_trigger_verification(client: BulkClient, secret_key: str, user: str) -> None:
    print("TRAILING STOP VERIFICATION:")
    ticker = client.get_ticker("BTC-USD")
    print("TRAILING VERIFY TICKER BTC-USD:")
    print(ticker)

    before = snapshot_account_views(client, user)
    btc_position = next((position for position in before["account"].positions if position.symbol == "BTC-USD"), None)
    if btc_position is None or btc_position.size == 0:
        print("TRAILING VERDICT: no live BTC-USD position; fire path not proven.")
        return

    safe_size = get_safe_btc_size(client, ticker)
    position_size = abs(btc_position.size)
    if position_size < safe_size:
        print("TRAILING VERDICT: position smaller than safe min size; fire path not proven.")
        print("TRAILING POSITION SIZE:", position_size)
        print("TRAILING SAFE SIZE:", safe_size)
        return

    protected_is_long = btc_position.size > 0
    trailing_size = min(position_size, 0.5)
    trail_bps = 1
    step_bps = 1
    print(
        "TRAILING PARAMS:",
        {
            "protected_is_long": protected_is_long,
            "size": trailing_size,
            "trail_bps": trail_bps,
            "step_bps": step_bps,
        },
    )

    response = client.place_trailing_stop_order(
        secret_key=secret_key,
        symbol="BTC-USD",
        protected_is_long=protected_is_long,
        size=trailing_size,
        trail_bps=trail_bps,
        step_bps=step_bps,
        limit_price=None,
    )
    print_typed_response("TRAILING STOP RESPONSE:", response)

    root_oid = find_oid(response.statuses)

    after_registration = wait_for_account_change(client, user, before, attempts=10, delay=1.0)
    print_snapshot_delta("TRAILING REGISTRATION DELTA:", before, after_registration)
    _, registered_open_orders, _ = print_btc_relevant_candidates(
        "TRAILING REGISTRATION OBJECTS:",
        before,
        after_registration,
    )

    trailing_roots = [item for item in registered_open_orders if getattr(item, "trigger", None) is not None]
    print("TRAILING ROOT CANDIDATES:", len(trailing_roots))
    print("FIRST TRAILING ROOT:", trailing_roots[0] if trailing_roots else None)

    initial_root = next((item for item in registered_open_orders if getattr(item, "orderId", None) == root_oid), None)
    initial_trigger = getattr(initial_root, "trigger", None) if initial_root is not None else None

    after_fire = wait_for_root_progress_or_completion(
        client,
        user,
        after_registration,
        root_oid=root_oid,
        attempts=30,
        delay=1.0,
    )
    print_snapshot_delta("TRAILING TRACKING/FIRE DELTA:", after_registration, after_fire)
    fire_fills, fire_open_orders, fire_order_history = print_btc_relevant_candidates(
        "TRAILING TRACKING/FIRE OBJECTS:",
        after_registration,
        after_fire,
    )

    latest_root = next((item for item in after_fire["open_orders"] if getattr(item, "orderId", None) == root_oid), None)
    latest_trigger = getattr(latest_root, "trigger", None) if latest_root is not None else None

    exact_triggered = [item for item in fire_order_history if str(getattr(item, "status", "")) == "triggered"]
    trigger_failed = [item for item in fire_order_history if str(getattr(item, "status", "")) == "triggerFailed"]
    terminal_exec = [
        item
        for item in fire_order_history
        if str(getattr(item, "status", "")) in {"filled", "partiallyFilled"}
    ]

    changed = initial_trigger != latest_trigger or latest_root is None

    print("TRAILING TRACKING CHANGED:", changed)
    print("TRAILING INITIAL TRIGGER:", initial_trigger)
    print("TRAILING LATEST TRIGGER:", latest_trigger)
    print("TRAILING EXACT TRIGGERED CANDIDATES:", len(exact_triggered))
    print("FIRST TRAILING EXACT TRIGGERED:", exact_triggered[0] if exact_triggered else None)
    print("TRAILING TRIGGER FAILED CANDIDATES:", len(trigger_failed))
    print("FIRST TRAILING TRIGGER FAILED:", trigger_failed[0] if trigger_failed else None)
    print("TRAILING TERMINAL EXECUTION CANDIDATES:", len(terminal_exec))
    print("FIRST TRAILING TERMINAL EXECUTION:", terminal_exec[0] if terminal_exec else None)
    print("TRAILING FIRE FILL CANDIDATES:", len(fire_fills))
    print("FIRST TRAILING FIRE FILL:", fire_fills[0] if fire_fills else None)

    trailing_fire_observed = bool(terminal_exec or fire_fills)

    if trailing_fire_observed:
        print("TRAILING VERDICT: fire path observed in this run.")
    else:
        print("TRAILING VERDICT: only registration/tracking observed; fire path not proven in this run.")

    if fire_open_orders:
        cleanup = client.cancel_all(secret_key=secret_key, symbols=["BTC-USD"])
        print_typed_response("TRAILING STOP CLEANUP:", cleanup)
    else:
        print("TRAILING STOP CLEANUP: not needed")


def run_trigger_basket_fire_verification(client: BulkClient, secret_key: str, user: str) -> None:
    print("TRIGGER BASKET FIRE VERIFICATION:")
    ticker = client.get_ticker("BTC-USD")
    print("TRIGGER FIRE TICKER BTC-USD:")
    print(ticker)

    size = get_safe_btc_size(client, ticker)
    before = snapshot_account_views(client, user)
    trigger_price = round(ticker.lastPrice * 0.5, 2)

    response = client.place_trigger_basket_order(
        secret_key=secret_key,
        symbol="BTC-USD",
        direction_above=True,
        trigger_price=trigger_price,
        actions=[
            {
                "type": "order",
                "symbol": "BTC-USD",
                "is_buy": True,
                "price": 0.0,
                "size": size,
                "reduce_only": False,
                "order_type": {"type": "market"},
            }
        ],
    )
    print_typed_response("TRIGGER BASKET FIRE RESPONSE:", response)

    after = wait_for_account_change(client, user, before, attempts=10, delay=1.0)
    print_snapshot_delta("TRIGGER BASKET FIRE ACCOUNT DELTA:", before, after)
    new_fills, new_open_orders, new_order_history = print_btc_relevant_candidates("TRIGGER BASKET FIRE RELEVANT OBJECTS:", before, after)

    child_orders = [item for item in new_order_history if getattr(item, "trigger", None) is None]
    print("TRIGGER BASKET NESTED FILL CANDIDATES:", len(new_fills))
    print("FIRST TRIGGER BASKET NESTED FILL:", new_fills[0] if new_fills else None)
    print("TRIGGER BASKET CHILD ORDER HISTORY CANDIDATES:", len(child_orders))
    print("FIRST TRIGGER BASKET CHILD ORDER HISTORY:", child_orders[0] if child_orders else None)

    if new_open_orders:
        cleanup = client.cancel_all(secret_key=secret_key, symbols=["BTC-USD"])
        print_typed_response("TRIGGER BASKET FIRE CLEANUP:", cleanup)
    else:
        print("TRIGGER BASKET FIRE CLEANUP: not needed")


def run_on_fill_execution_verification(client: BulkClient, secret_key: str, user: str) -> None:
    print("ON-FILL EXECUTION VERIFICATION:")
    ticker = client.get_ticker("BTC-USD")
    print("ON-FILL VERIFY TICKER BTC-USD:")
    print(ticker)

    safe_size = get_safe_btc_size(client, ticker)
    before = snapshot_account_views(client, user)

    response = client.place_on_fill_order(
        secret_key=secret_key,
        parent_action={
            "type": "order",
            "symbol": "BTC-USD",
            "is_buy": True,
            "price": round(ticker.lastPrice * 1.2, 2),
            "size": safe_size,
            "reduce_only": False,
            "order_type": {"type": "limit", "tif": "IOC"},
        },
        child_actions=[
            {
                "type": "stop",
                "symbol": "BTC-USD",
                "is_buy": False,
                "size": safe_size,
                "trigger_price": round(ticker.lastPrice * 0.5, 2),
                "limit_price": round(ticker.lastPrice * 0.5 * 0.999, 2),
            }
        ],
    )
    print_typed_response("ON-FILL EXECUTION RESPONSE:", response)

    after = wait_for_account_change(client, user, before, attempts=10, delay=1.0)
    print_snapshot_delta("ON-FILL EXECUTION ACCOUNT DELTA:", before, after)

    matching_child_orders = [
        order
        for order in after["open_orders"]
        if getattr(order, "symbol", None) == "BTC-USD" and getattr(order, "trigger", None) is not None
    ]
    print("ON-FILL CHILD STOP CANDIDATES:", len(matching_child_orders))
    print("FIRST ON-FILL CHILD STOP:", matching_child_orders[0] if matching_child_orders else None)

    if matching_child_orders:
        cleanup = client.cancel_all(secret_key=secret_key, symbols=["BTC-USD"])
        print_typed_response("ON-FILL EXECUTION CLEANUP:", cleanup)
    else:
        print("ON-FILL EXECUTION CLEANUP: not needed")


def run_behavioral_verification(client: BulkClient, secret_key: str, user: str) -> None:
    print("BEHAVIORAL VERIFICATION PATH:")
    run_stop_trigger_verification(client, secret_key, user)
    run_take_profit_trigger_verification(client, secret_key, user)
    run_range_trigger_verification(client, secret_key, user)
    run_trailing_trigger_verification(client, secret_key, user)
    run_trigger_basket_fire_verification(client, secret_key, user)
    run_on_fill_execution_verification(client, secret_key, user)


def main() -> None:
    secret_key = os.environ.get("BULK_SECRET_KEY")

    if not secret_key:
        print("BULK_SECRET_KEY is not set.")
        raise SystemExit(1)

    signer = BulkSigner(secret_key)
    user = signer.account

    with BulkClient() as client:
        if not run_basic(client, secret_key):
            return
        run_conditional_registration(client, secret_key)
        run_behavioral_verification(client, secret_key, user)


if __name__ == "__main__":
    main()