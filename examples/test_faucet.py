from __future__ import annotations

import json
import os
from pathlib import Path
import sys

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


def status_text(response) -> str:
    return json.dumps(response.raw, sort_keys=True, default=str).lower()


def print_typed_response(label: str, response) -> None:
    print(label)
    print(response)
    print("RESPONSE STATUS NAMES:", status_names(response))
    print("FIRST STATUS:", response.statuses[0] if response.statuses else None)


def is_rate_limited(response) -> bool:
    text = status_text(response)
    expected_words = ["rate limit", "already", "24", "cooldown", "claimed"]
    return "depositFailed" in status_names(response) and any(word in text for word in expected_words)


def main() -> None:
    secret_key = require_env("BULK_SECRET_KEY")
    signer = BulkSigner(secret_key)
    user = signer.account

    print("MAIN ACCOUNT:", user)

    with BulkClient() as client:
        payload = signer.sign_faucet()
        response = client.submit_order(payload)
        print_typed_response("FAUCET RESPONSE", response)

    names = status_names(response)
    deposit_ok = "deposit" in names
    rate_limited = is_rate_limited(response)
    submit_ok = response.top_level_status == "ok" and (deposit_ok or rate_limited)

    print("FORENSIC VERDICT:")
    print(f"submit_ok={submit_ok}")
    print(f"deposit_ok={deposit_ok}")
    print(f"rate_limited={rate_limited}")


if __name__ == "__main__":
    main()
