from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bulk_sdk import BulkClient
from bulk_sdk.signer import BulkSigner


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"{name} is not set.")
        raise SystemExit(1)
    return value


def status_names(response) -> list[str]:
    names: list[str] = []

    for status in response.statuses:
        if isinstance(status, dict):
            names.extend(str(name) for name in status)

    if not names and response.top_level_status == "error":
        names.append("error")

    return names


def print_typed_response(label: str, response) -> None:
    print(label)
    print(response)
    print(f"{label.replace(' RESPONSE', ' STATUS NAMES')}:", status_names(response))
    print("FIRST STATUS:", response.statuses[0] if response.statuses else None)


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


def status_text(response) -> str:
    return json.dumps(response.raw, sort_keys=True, default=str).lower()


def has_status(response, name: str) -> bool:
    return name in status_names(response)


def is_soft_status(response, words: list[str]) -> bool:
    text = status_text(response)
    return any(word in text for word in words)


def agent_wallet_usable(response) -> bool:
    return has_status(response, "agentWallet") or (
        has_status(response, "agentWalletFailed")
        and is_soft_status(response, ["already", "exists", "duplicate"])
    )


def agent_wallet_removed_or_absent(response) -> bool:
    return has_status(response, "agentWallet") or (
        has_status(response, "agentWalletFailed")
        and is_soft_status(response, ["not found", "missing", "absent", "does not exist"])
    )


def get_safe_btc_size(client: BulkClient, ticker, requested_size: float = 0.001) -> float:
    market = next(item for item in client.get_markets() if item.symbol == "BTC-USD")
    raw_min_size = max(
        requested_size,
        market.lotSize,
        market.minNotional / max(ticker.lastPrice, 1.0),
    )
    steps = max(1, math.ceil(raw_min_size / market.lotSize))
    return round(steps * market.lotSize, market.sizePrecision)


def sign_agent_wallet_payload(main_signer: BulkSigner, agent_pubkey: str, delete: bool) -> dict:
    return main_signer.sign_agent_wallet(agent_pubkey, delete=delete)


def sign_agent_order_payload(
    order: dict,
    main_account: str,
    agent_pubkey: str,
    agent_signer: BulkSigner,
) -> dict:
    if agent_signer.account != agent_pubkey:
        raise ValueError("agent signer account does not match agent pubkey")
    return agent_signer.sign_as_agent(order, account=main_account)


def run_register_agent_wallet(
    client: BulkClient,
    main_signer: BulkSigner,
    agent_pubkey: str,
) -> tuple[bool, object]:
    payload = sign_agent_wallet_payload(main_signer, agent_pubkey, delete=False)
    response = client.submit_order(payload)
    print_typed_response("REGISTER AGENT RESPONSE", response)
    usable = agent_wallet_usable(response)
    print("REGISTER FORENSIC VERDICT:", "usable" if usable else "not usable")
    return usable, response


def run_agent_trading_check(
    client: BulkClient,
    main_account: str,
    agent_signer: BulkSigner,
    agent_pubkey: str,
) -> tuple[bool, bool]:
    ticker = client.get_ticker("BTC-USD")
    size = get_safe_btc_size(client, ticker)
    price = round(max(ticker.lastPrice * 0.98, ticker.markPrice * 0.98), 2)

    place_payload = sign_agent_order_payload(
        {
            "type": "order",
            "symbol": "BTC-USD",
            "is_buy": True,
            "price": price,
            "size": size,
            "reduce_only": False,
            "order_type": {"type": "limit", "tif": "GTC"},
        },
        main_account=main_account,
        agent_pubkey=agent_pubkey,
        agent_signer=agent_signer,
    )
    place_response = client.submit_order(place_payload)
    print_typed_response("AGENT PLACE RESPONSE", place_response)

    oid = find_oid(place_response.statuses)
    place_ok = any(name in status_names(place_response) for name in ["resting", "working", "filled", "partiallyFilled"])
    if any(name in status_names(place_response) for name in ["filled", "partiallyFilled"]):
        print("agent order executed immediately, cancel path not proven in this run")
        return place_ok, False

    if oid is None:
        print("AGENT CANCEL RESPONSE")
        print("skipped: no oid found in agent place response")
        print("AGENT CANCEL STATUS NAMES:", [])
        return place_ok, False

    cancel_payload = sign_agent_order_payload(
        {
            "type": "cancel",
            "symbol": "BTC-USD",
            "order_id": oid,
        },
        main_account=main_account,
        agent_pubkey=agent_pubkey,
        agent_signer=agent_signer,
    )
    cancel_response = client.submit_order(cancel_payload)
    print_typed_response("AGENT CANCEL RESPONSE", cancel_response)
    cancel_ok = has_status(cancel_response, "cancelled")
    return place_ok, cancel_ok


def run_remove_agent_wallet(
    client: BulkClient,
    main_signer: BulkSigner,
    agent_pubkey: str,
) -> tuple[bool, object]:
    payload = sign_agent_wallet_payload(main_signer, agent_pubkey, delete=True)
    response = client.submit_order(payload)
    print_typed_response("REMOVE AGENT RESPONSE", response)
    removed = agent_wallet_removed_or_absent(response)
    print("REMOVE FORENSIC VERDICT:", "removed_or_absent" if removed else "not removed")
    return removed, response


def main() -> None:
    secret_key = require_env("BULK_SECRET_KEY")
    agent_secret_key = require_env("BULK_AGENT_SECRET_KEY")
    agent_pubkey = require_env("BULK_AGENT_PUBLIC_KEY")

    main_signer = BulkSigner(secret_key)
    agent_signer = BulkSigner(agent_secret_key)
    main_account = main_signer.account
    derived_agent_pubkey = agent_signer.account

    print("MAIN ACCOUNT:", main_account)
    print("AGENT PUBKEY ENV:", agent_pubkey)
    print("AGENT PUBKEY DERIVED:", derived_agent_pubkey)

    if agent_pubkey != derived_agent_pubkey:
        print("BULK_AGENT_PUBLIC_KEY does not match BULK_AGENT_SECRET_KEY.")
        raise SystemExit(1)

    with BulkClient() as client:
        register_ok, _ = run_register_agent_wallet(client, main_signer, agent_pubkey)
        time.sleep(1)
        agent_order_ok, agent_cancel_ok = run_agent_trading_check(
            client,
            main_account=main_account,
            agent_signer=agent_signer,
            agent_pubkey=agent_pubkey,
        )
        time.sleep(1)
        remove_ok, _ = run_remove_agent_wallet(client, main_signer, agent_pubkey)

    print("FORENSIC VERDICT:")
    print(f"register_ok={register_ok}")
    print(f"agent_order_ok={agent_order_ok}")
    print(f"agent_cancel_ok={agent_cancel_ok}")
    print(f"remove_ok={remove_ok}")


if __name__ == "__main__":
    main()
