"""Minimal signed transaction wrapper for BULK trading."""

from __future__ import annotations

from typing import Any

from bulk_keychain import Keypair, Signer


class BulkSigner:
    def __init__(self, secret_key: str) -> None:
        self._keypair = Keypair.from_base58(secret_key)
        self._signer = Signer(self._keypair)
        self.account = self._keypair.pubkey

    def _envelope(self, payload: dict[str, Any]) -> dict[str, Any]:
        signed = self._signer.sign(payload)
        return dict(signed)

    def _group_envelope(self, payloads: list[dict[str, Any]]) -> dict[str, Any]:
        signed = self._signer.sign_group(payloads)
        return dict(signed)

    def sign_limit_order(
        self,
        symbol: str,
        is_buy: bool,
        price: float,
        size: float,
        tif: str = "GTC",
        reduce_only: bool = False,
    ) -> dict[str, Any]:
        payload = {
            "type": "order",
            "symbol": symbol,
            "is_buy": is_buy,
            "price": price,
            "size": size,
            "reduce_only": reduce_only,
            "order_type": {
                "type": "limit",
                "tif": tif,
            },
        }
        return self._envelope(payload)

    def sign_market_order(
        self,
        symbol: str,
        is_buy: bool,
        size: float,
        reduce_only: bool = False,
    ) -> dict[str, Any]:
        payload = {
            "type": "order",
            "symbol": symbol,
            "is_buy": is_buy,
            "price": 0.0,
            "size": size,
            "reduce_only": reduce_only,
            "order_type": {
                "type": "market",
            },
        }
        return self._envelope(payload)

    def sign_cancel_order(self, symbol: str, order_id: str) -> dict[str, Any]:
        payload = {
            "type": "cancel",
            "symbol": symbol,
            "order_id": order_id,
        }
        return self._envelope(payload)

    def sign_cancel_all(self, symbols: list[str] | None = None) -> dict[str, Any]:
        payload = {
            "type": "cancel_all",
            "symbols": [] if symbols is None else symbols,
        }
        return self._envelope(payload)

    def sign_modify_order(self, symbol: str, order_id: str, amount: float) -> dict[str, Any]:
        payload = {
            "type": "modify",
            "symbol": symbol,
            "order_id": order_id,
            "amount": amount,
        }
        return self._envelope(payload)

    def sign_stop_order(
        self,
        symbol: str,
        direction_above: bool,
        size: float,
        trigger_price: float,
        limit_price: float | None = None,
    ) -> dict[str, Any]:
        payload = {
            "type": "stop",
            "symbol": symbol,
            "is_buy": direction_above,
            "size": size,
            "trigger_price": trigger_price,
        }
        if limit_price is not None:
            payload["limit_price"] = limit_price
        return self._envelope(payload)

    def sign_take_profit_order(
        self,
        symbol: str,
        direction_above: bool,
        size: float,
        trigger_price: float,
        limit_price: float | None = None,
    ) -> dict[str, Any]:
        payload = {
            "type": "take_profit",
            "symbol": symbol,
            "is_buy": direction_above,
            "size": size,
            "trigger_price": trigger_price,
        }
        if limit_price is not None:
            payload["limit_price"] = limit_price
        return self._envelope(payload)

    def sign_range_order(
        self,
        symbol: str,
        direction_above: bool,
        size: float,
        lower_trigger: float,
        upper_trigger: float,
        lower_limit: float | None = None,
        upper_limit: float | None = None,
    ) -> dict[str, Any]:
        payload = {
            "type": "range",
            "symbol": symbol,
            "is_buy": direction_above,
            "size": size,
            "pmin": lower_trigger,
            "pmax": upper_trigger,
        }
        if lower_limit is not None:
            payload["lmin"] = lower_limit
        if upper_limit is not None:
            payload["lmax"] = upper_limit
        return self._envelope(payload)

    def sign_trailing_stop_order(
        self,
        symbol: str,
        protected_is_long: bool,
        size: float,
        trail_bps: int,
        step_bps: int,
        limit_price: float | None = None,
    ) -> dict[str, Any]:
        payload = {
            "type": "trailing_stop",
            "symbol": symbol,
            "is_buy": protected_is_long,
            "size": size,
            "trail_bps": trail_bps,
            "step_bps": step_bps,
        }
        if limit_price is not None:
            payload["limit_price"] = limit_price
        return self._envelope(payload)

    def sign_trigger_basket_order(
        self,
        symbol: str,
        direction_above: bool,
        trigger_price: float,
        actions: list[dict],
    ) -> dict[str, Any]:
        payload = {
            "type": "trig",
            "symbol": symbol,
            "is_buy": direction_above,
            "trigger_price": trigger_price,
            "actions": actions,
        }
        return self._envelope(payload)

    def sign_on_fill_order(
        self,
        parent_action: dict,
        child_actions: list[dict],
    ) -> dict[str, Any]:
        payloads = [
            parent_action,
            {
                "type": "of",
                "p": 0,
                "actions": child_actions,
            },
        ]
        return self._group_envelope(payloads)
