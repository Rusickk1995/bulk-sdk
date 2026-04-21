from __future__ import annotations

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
    print("RESPONSE STATUS NAMES:", status_names(response))
    print("FIRST STATUS:", response.statuses[0] if response.statuses else None)


def response_submit_ok(response) -> bool:
    if response.top_level_status != "ok":
        return False

    if not response.statuses:
        return True

    return any(
        isinstance(status, dict)
        and isinstance(status.get("ack"), dict)
        and status["ack"].get("ok") is True
        for status in response.statuses
    )


def get_btc_leverage(account) -> float | None:
    for setting in account.leverageSettings:
        if setting.symbol == "BTC-USD":
            return float(setting.leverage)
    return None


def candidate_leverages(current: float) -> list[float]:
    ladder = [45.0, 40.0, 35.0, 30.0, 25.0, 20.0, 15.0, 10.0, 5.0]
    return [value for value in ladder if 1.0 <= value <= 50.0 and value < current]


def wait_for_btc_leverage(
    client: BulkClient,
    user: str,
    expected: float,
    attempts: int = 10,
    delay: float = 1.0,
) -> float | None:
    latest: float | None = None

    for _ in range(attempts):
        time.sleep(delay)
        account = client.get_full_account(user)
        latest = get_btc_leverage(account)
        if latest == expected:
            return latest

    return latest


def submit_user_settings(client: BulkClient, signer: BulkSigner, leverage: float):
    payload = signer.sign_user_settings({"BTC-USD": leverage})
    return client.submit_order(payload)


def main() -> None:
    secret_key = require_env("BULK_SECRET_KEY")
    signer = BulkSigner(secret_key)
    user = signer.account

    print("MAIN ACCOUNT:", user)

    with BulkClient() as client:
        initial_account = client.get_full_account(user)
        initial_leverage = get_btc_leverage(initial_account)

        if initial_leverage is None:
            print("INITIAL BTC-USD LEVERAGE: not found")
            print("FORENSIC VERDICT:")
            print("submit_ok=False")
            print("applied_ok=False")
            print("restore_ok=False")
            return

        targets = candidate_leverages(initial_leverage)
        print("INITIAL BTC-USD LEVERAGE:", initial_leverage)
        print("TARGET BTC-USD LEVERAGE CANDIDATES:", targets)

        submit_ok = False
        applied_ok = False
        restore_ok = False
        applied_leverage: float | None = None
        updated_leverage: float | None = initial_leverage

        for target_leverage in targets:
            print("TRY TARGET BTC-USD LEVERAGE:", target_leverage)
            update_response = submit_user_settings(client, signer, target_leverage)
            print_typed_response("UPDATE USER SETTINGS RESPONSE", update_response)
            submit_ok = submit_ok or response_submit_ok(update_response)

            updated_leverage = wait_for_btc_leverage(client, user, target_leverage)
            print("UPDATED BTC-USD LEVERAGE:", updated_leverage)

            if updated_leverage == target_leverage:
                applied_ok = True
                applied_leverage = target_leverage
                break

        if applied_leverage is None:
            print("NO ACCEPTABLE TARGET BTC-USD LEVERAGE APPLIED FOR CURRENT ACCOUNT STATE")
        else:
            restore_response = submit_user_settings(client, signer, initial_leverage)
            print_typed_response("RESTORE USER SETTINGS RESPONSE", restore_response)

            restored_leverage = wait_for_btc_leverage(client, user, initial_leverage)
            print("RESTORED BTC-USD LEVERAGE:", restored_leverage)
            restore_ok = restored_leverage == initial_leverage

    print("FORENSIC VERDICT:")
    print(f"submit_ok={submit_ok}")
    print(f"applied_ok={applied_ok}")
    print(f"restore_ok={restore_ok}")


if __name__ == "__main__":
    main()
