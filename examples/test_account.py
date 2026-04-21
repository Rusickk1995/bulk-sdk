from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bulk_sdk import BulkClient


def print_list_result(label: str, data) -> None:
    print(f"{label} TYPE:", type(data).__name__)
    print(f"{label} LENGTH:", len(data))
    print(f"{label} FIRST:", data[0] if data else None)


def main() -> None:
    with BulkClient() as client:
        user = "3ctpRKjDYT3aAhuwbVVqEDRyRTXToRF8iddD5fFiDqvE"
        account = client.get_full_account(user)
        print("MARGIN:", account.margin)
        print("POSITIONS COUNT:", len(account.positions))
        print("FIRST POSITION:", account.positions[0] if account.positions else None)
        print("OPEN ORDERS COUNT:", len(account.openOrders))
        print("FEE TIERS:", account.feeTiers)
        print("LEVERAGE SETTINGS COUNT:", len(account.leverageSettings))

        open_orders_raw = client.get_open_orders_raw(user)
        print_list_result("OPEN ORDERS RAW", open_orders_raw)

        open_orders_typed = client.get_open_orders_typed(user)
        print_list_result("OPEN ORDERS TYPED", open_orders_typed)

        fills_raw = client.get_fills_raw(user)
        print_list_result("FILLS RAW", fills_raw)

        fills = client.get_fills(user)
        print_list_result("FILLS TYPED", fills)

        positions_raw = client.get_positions_raw(user)
        print_list_result("CLOSED POSITIONS RAW", positions_raw)

        closed_positions = client.get_closed_positions(user)
        print_list_result("CLOSED POSITIONS TYPED", closed_positions)

        funding_history_raw = client.get_funding_history_raw(user)
        print_list_result("FUNDING HISTORY RAW", funding_history_raw)

        funding_history = client.get_funding_history(user)
        print_list_result("FUNDING HISTORY TYPED", funding_history)

        order_history_raw = client.get_order_history_raw(user)
        print_list_result("ORDER HISTORY RAW", order_history_raw)

        order_history = client.get_order_history(user)
        print_list_result("ORDER HISTORY TYPED", order_history)

        fee_tier_raw = client.get_fee_tier_raw(user, "BTC-USD")
        print("FEE TIER RAW TYPE:", type(fee_tier_raw).__name__)
        print("FEE TIER RAW LENGTH:", len(fee_tier_raw) if isinstance(fee_tier_raw, list) else None)
        print("FEE TIER RAW FIRST:", fee_tier_raw[0] if isinstance(fee_tier_raw, list) and fee_tier_raw else None)

        fee_tier = client.get_fee_tier(user, "BTC-USD")
        print("FEE TIER TYPED:", fee_tier)


if __name__ == "__main__":
    main()
