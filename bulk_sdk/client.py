"""HTTP client for the BULK Exchange HTTP MVP."""

from __future__ import annotations

import httpx

from .constants import BASE_URL, HTTP_TIMEOUT
from .exceptions import BulkAPIError
from .models import (
    AccountState,
    Candle,
    ClosedPositionItem,
    ExchangeStats,
    FeeState,
    FeeTier,
    FeeTierState,
    FillItem,
    FundingPaymentItem,
    LeverageSetting,
    Margin,
    Market,
    OpenOrder,
    OpenOrderItem,
    OrderHistoryItem,
    OrderBook,
    OrderBookLevel,
    OrderResponse,
    OrderResponseData,
    OrderStatusEntry,
    Position,
    RiskSurfaces,
    Ticker,
)
from .signer import BulkSigner


class BulkClient:
    def __init__(self, base_url: str = BASE_URL, timeout: float = HTTP_TIMEOUT) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(base_url=self.base_url, timeout=self.timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "BulkClient":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def _get(self, path: str, params: dict | None = None):
        response = self._client.get(path, params=params)

        if response.status_code != 200:
            try:
                raw = response.json()
            except ValueError:
                raw = response.text

            raise BulkAPIError(
                f"GET {path} failed",
                status_code=response.status_code,
                raw=raw,
            )

        return response.json()

    def _post(self, path: str, json: dict | None = None):
        response = self._client.post(path, json=json)

        if response.status_code != 200:
            try:
                raw = response.json()
            except ValueError:
                raw = response.text

            raise BulkAPIError(
                f"POST {path} failed",
                status_code=response.status_code,
                raw=raw,
            )

        return response.json()

    def get_markets(self) -> list[Market]:
        data = self._get("/exchangeInfo")
        return [
            Market(
                symbol=item["symbol"],
                baseAsset=item["baseAsset"],
                quoteAsset=item["quoteAsset"],
                status=item["status"],
                pricePrecision=item["pricePrecision"],
                sizePrecision=item["sizePrecision"],
                tickSize=item["tickSize"],
                lotSize=item["lotSize"],
                minNotional=item["minNotional"],
                maxLeverage=item["maxLeverage"],
                orderTypes=item.get("orderTypes", []),
                timeInForces=item.get("timeInForces", []),
                raw=item,
            )
            for item in data
        ]

    def get_ticker(self, symbol: str) -> Ticker:
        data = self._get(f"/ticker/{symbol}")
        return Ticker(
            symbol=data["symbol"],
            priceChange=data["priceChange"],
            priceChangePercent=data["priceChangePercent"],
            lastPrice=data["lastPrice"],
            highPrice=data["highPrice"],
            lowPrice=data["lowPrice"],
            volume=data["volume"],
            quoteVolume=data["quoteVolume"],
            markPrice=data["markPrice"],
            oraclePrice=data["oraclePrice"],
            openInterest=data["openInterest"],
            fundingRate=data["fundingRate"],
            regime=data["regime"],
            regimeDt=data["regimeDt"],
            regimeVol=data["regimeVol"],
            regimeMv=data["regimeMv"],
            fairBookPx=data["fairBookPx"],
            fairVol=data["fairVol"],
            fairBias=data["fairBias"],
            timestamp=data["timestamp"],
            raw=data,
        )

    def get_order_book(
        self,
        symbol: str,
        nlevels: int = 10,
        aggregation: float | None = None,
    ) -> OrderBook:
        params = {
            "type": "l2book",
            "coin": symbol,
            "nlevels": nlevels,
        }
        if aggregation is not None:
            params["aggregation"] = aggregation

        data = self._get("/l2book", params=params)
        raw_levels = data.get("levels", [[], []])

        levels = [
            [
                OrderBookLevel(
                    px=level["px"],
                    sz=level["sz"],
                    n=level["n"],
                    raw=level,
                )
                for level in side
            ]
            for side in raw_levels
        ]

        return OrderBook(
            updateType=data["updateType"],
            symbol=data["symbol"],
            levels=levels,
            timestamp=data.get("timestamp"),
            raw=data,
        )

    def get_candles(
        self,
        symbol: str,
        interval: str,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[Candle]:
        params = {
            "symbol": symbol,
            "interval": interval,
        }
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time

        data = self._get("/klines", params=params)
        return [
            Candle(
                t=item["t"],
                T=item["T"],
                o=item["o"],
                h=item["h"],
                l=item["l"],
                c=item["c"],
                v=item["v"],
                n=item["n"],
                raw=item,
            )
            for item in data
        ]

    def get_stats(
        self,
        symbol: str | None = None,
        period: str | None = None,
    ) -> ExchangeStats:
        params = {}
        if symbol is not None:
            params["symbol"] = symbol
        if period is not None:
            params["period"] = period

        data = self._get("/stats", params=params or None)
        return ExchangeStats(
            timestamp=data["timestamp"],
            period=data["period"],
            volume=data.get("volume", {}),
            openInterest=data.get("openInterest", {}),
            funding=data.get("funding", {}),
            markets=data.get("markets", []),
            raw=data,
        )

    def get_risk_surfaces(self, symbol: str | None = None) -> RiskSurfaces:
        params = None
        if symbol is not None:
            params = {"market": symbol}

        data = self._get("/riskSurfaces", params=params)
        return RiskSurfaces(
            symbol=data["symbol"],
            liveRegime=data["liveRegime"],
            surfaces=data.get("surfaces", []),
            corrs=data.get("corrs", []),
            raw=data,
        )

    def get_fee_state(self) -> FeeState:
        data = self._get("/feeState")
        return FeeState(
            stamp=data["stamp"],
            slot=data["slot"],
            trackable_id=data.get("trackable_id", {}),
            global_policy_active=data.get("global_policy_active", False),
            instrument_overrides_active=data.get("instrument_overrides_active", 0),
            scheduled_global_depth=data.get("scheduled_global_depth", 0),
            scheduled_total_depth=data.get("scheduled_total_depth", 0),
            next_activation_slot=data.get("next_activation_slot"),
            settled_fills=data.get("settled_fills", 0),
            total_maker_fees=data.get("total_maker_fees", 0.0),
            total_taker_fees=data.get("total_taker_fees", 0.0),
            total_protocol_settlement=data.get("total_protocol_settlement", 0.0),
            scopes=data.get("scopes", []),
            raw=data,
        )

    def submit_order_raw(self, payload: dict):
        return self._post("/order", json=payload)

    def parse_order_response(self, data: dict) -> OrderResponse:
        top_level_status = data.get("status")
        response = data.get("response")

        response_type: str | None = None
        statuses: list[dict] = []

        if isinstance(response, dict):
            response_type = response.get("type")
            response_data_raw = response.get("data", {})
            if isinstance(response_data_raw, dict):
                raw_statuses = response_data_raw.get("statuses", [])
                if isinstance(raw_statuses, list):
                    status_entries = [
                        OrderStatusEntry(raw=item)
                        for item in raw_statuses
                        if isinstance(item, dict)
                    ]
                    response_data = OrderResponseData(
                        statuses=[entry.raw for entry in status_entries],
                        raw=response_data_raw,
                    )
                    statuses = response_data.statuses

        return OrderResponse(
            top_level_status=top_level_status,
            response_type=response_type,
            statuses=statuses,
            raw=data,
        )

    def submit_order(self, payload: dict) -> OrderResponse:
        data = self.submit_order_raw(payload)
        return self.parse_order_response(data)

    def _parse_side(self, side: str) -> bool:
        normalized_side = side.strip().lower()
        if normalized_side == "buy":
            return True
        if normalized_side == "sell":
            return False
        raise ValueError("side must be either 'buy' or 'sell'")

    def place_limit_order(
        self,
        secret_key: str,
        symbol: str,
        side: str,
        price: float,
        size: float,
        tif: str = "GTC",
        reduce_only: bool = False,
    ) -> OrderResponse:
        is_buy = self._parse_side(side)
        signer = BulkSigner(secret_key)
        payload = signer.sign_limit_order(
            symbol=symbol,
            is_buy=is_buy,
            price=price,
            size=size,
            tif=tif,
            reduce_only=reduce_only,
        )
        return self.submit_order(payload)

    def cancel_order(self, secret_key: str, symbol: str, order_id: str) -> OrderResponse:
        signer = BulkSigner(secret_key)
        payload = signer.sign_cancel_order(symbol, order_id)
        return self.submit_order(payload)

    def place_market_order(
        self,
        secret_key: str,
        symbol: str,
        side: str,
        size: float,
        reduce_only: bool = False,
    ) -> OrderResponse:
        is_buy = self._parse_side(side)
        signer = BulkSigner(secret_key)
        payload = signer.sign_market_order(
            symbol=symbol,
            is_buy=is_buy,
            size=size,
            reduce_only=reduce_only,
        )
        return self.submit_order(payload)

    def cancel_all(self, secret_key: str, symbols: list[str] | None = None) -> OrderResponse:
        signer = BulkSigner(secret_key)
        payload = signer.sign_cancel_all(symbols)
        return self.submit_order(payload)

    def modify_order(
        self,
        secret_key: str,
        symbol: str,
        order_id: str,
        amount: float,
    ) -> OrderResponse:
        signer = BulkSigner(secret_key)
        payload = signer.sign_modify_order(symbol, order_id, amount)
        return self.submit_order(payload)

    def place_stop_order(
        self,
        secret_key: str,
        symbol: str,
        direction_above: bool,
        size: float,
        trigger_price: float,
        limit_price: float | None = None,
    ) -> OrderResponse:
        signer = BulkSigner(secret_key)
        payload = signer.sign_stop_order(
            symbol=symbol,
            direction_above=direction_above,
            size=size,
            trigger_price=trigger_price,
            limit_price=limit_price,
        )
        return self.submit_order(payload)

    def place_take_profit_order(
        self,
        secret_key: str,
        symbol: str,
        direction_above: bool,
        size: float,
        trigger_price: float,
        limit_price: float | None = None,
    ) -> OrderResponse:
        signer = BulkSigner(secret_key)
        payload = signer.sign_take_profit_order(
            symbol=symbol,
            direction_above=direction_above,
            size=size,
            trigger_price=trigger_price,
            limit_price=limit_price,
        )
        return self.submit_order(payload)

    def place_range_order(
        self,
        secret_key: str,
        symbol: str,
        direction_above: bool,
        size: float,
        lower_trigger: float,
        upper_trigger: float,
        lower_limit: float | None = None,
        upper_limit: float | None = None,
    ) -> OrderResponse:
        signer = BulkSigner(secret_key)
        payload = signer.sign_range_order(
            symbol=symbol,
            direction_above=direction_above,
            size=size,
            lower_trigger=lower_trigger,
            upper_trigger=upper_trigger,
            lower_limit=lower_limit,
            upper_limit=upper_limit,
        )
        return self.submit_order(payload)

    def place_trailing_stop_order(
        self,
        secret_key: str,
        symbol: str,
        protected_is_long: bool,
        size: float,
        trail_bps: int,
        step_bps: int,
        limit_price: float | None = None,
    ) -> OrderResponse:
        signer = BulkSigner(secret_key)
        payload = signer.sign_trailing_stop_order(
            symbol=symbol,
            protected_is_long=protected_is_long,
            size=size,
            trail_bps=trail_bps,
            step_bps=step_bps,
            limit_price=limit_price,
        )
        return self.submit_order(payload)

    def place_trigger_basket_order(
        self,
        secret_key: str,
        symbol: str,
        direction_above: bool,
        trigger_price: float,
        actions: list[dict],
    ) -> OrderResponse:
        signer = BulkSigner(secret_key)
        payload = signer.sign_trigger_basket_order(
            symbol=symbol,
            direction_above=direction_above,
            trigger_price=trigger_price,
            actions=actions,
        )
        return self.submit_order(payload)

    def place_on_fill_order(
        self,
        secret_key: str,
        parent_action: dict,
        child_actions: list[dict],
    ) -> OrderResponse:
        signer = BulkSigner(secret_key)
        payload = signer.sign_on_fill_order(parent_action, child_actions)
        return self.submit_order(payload)

    def query_account_raw(self, payload: dict) -> dict | list:
        return self._post("/account", json=payload)

    def _unwrap_account_items(self, data: dict | list, key: str) -> list[dict]:
        if not isinstance(data, list):
            raise BulkAPIError(f"Unexpected {key} response shape", raw=data)

        items: list[dict] = []
        for item in data:
            if not isinstance(item, dict):
                raise BulkAPIError(f"Unexpected {key} response shape", raw=data)
            value = item.get(key)
            if not isinstance(value, dict):
                raise BulkAPIError(f"Unexpected {key} response shape", raw=data)
            items.append(value)

        return items

    def get_full_account(self, user: str) -> AccountState:
        data = self.query_account_raw({"type": "fullAccount", "user": user})

        if not isinstance(data, list) or not data:
            raise BulkAPIError("Unexpected fullAccount response shape", raw=data)

        first_item = data[0]
        if not isinstance(first_item, dict) or "fullAccount" not in first_item:
            raise BulkAPIError("Unexpected fullAccount response shape", raw=data)

        full_account = first_item["fullAccount"]

        margin_data = full_account["margin"]
        positions_data = full_account.get("positions", [])
        open_orders_data = full_account.get("openOrders", [])
        fee_tiers_data = full_account.get("feeTiers", [])
        leverage_settings_data = full_account.get("leverageSettings", [])

        margin = Margin(
            totalBalance=margin_data["totalBalance"],
            availableBalance=margin_data["availableBalance"],
            marginUsed=margin_data["marginUsed"],
            notional=margin_data["notional"],
            realizedPnl=margin_data["realizedPnl"],
            unrealizedPnl=margin_data["unrealizedPnl"],
            fees=margin_data["fees"],
            funding=margin_data["funding"],
            raw=margin_data,
        )

        positions = [
            Position(
                symbol=item["symbol"],
                size=item["size"],
                price=item["price"],
                fairPrice=item["fairPrice"],
                notional=item["notional"],
                realizedPnl=item["realizedPnl"],
                unrealizedPnl=item["unrealizedPnl"],
                leverage=item["leverage"],
                liquidationPrice=item["liquidationPrice"],
                fees=item["fees"],
                funding=item["funding"],
                maintenanceMargin=item["maintenanceMargin"],
                lambda_=item["lambda"],
                riskAllocation=item["riskAllocation"],
                raw=item,
            )
            for item in positions_data
        ]

        open_orders = [OpenOrder(raw=item) for item in open_orders_data]

        fee_tiers = [
            FeeTier(
                symbol=item["symbol"],
                rollingVolume=item["rollingVolume"],
                tierIndex=item["tierIndex"],
                tierThreshold=item["tierThreshold"],
                makerBps=item["makerBps"],
                takerBps=item["takerBps"],
                windowDays=item["windowDays"],
                raw=item,
            )
            for item in fee_tiers_data
        ]

        leverage_settings = [
            LeverageSetting(
                symbol=item["symbol"],
                leverage=item["leverage"],
                raw=item,
            )
            for item in leverage_settings_data
        ]

        return AccountState(
            margin=margin,
            positions=positions,
            openOrders=open_orders,
            feeTiers=fee_tiers,
            leverageSettings=leverage_settings,
            raw=full_account,
        )

    def get_positions(self, user: str) -> list[Position]:
        return self.get_full_account(user).positions

    def get_open_orders(self, user: str) -> list[OpenOrder]:
        return self.get_full_account(user).openOrders

    def get_balance(self, user: str) -> Margin:
        return self.get_full_account(user).margin

    def get_open_orders_raw(self, user: str) -> dict | list:
        return self.query_account_raw({"type": "openOrders", "user": user})

    def get_fills_raw(self, user: str) -> dict | list:
        return self.query_account_raw({"type": "fills", "user": user})

    def get_positions_raw(self, user: str) -> dict | list:
        return self.query_account_raw({"type": "positions", "user": user})

    def get_funding_history_raw(self, user: str) -> dict | list:
        return self.query_account_raw({"type": "fundingHistory", "user": user})

    def get_order_history_raw(self, user: str) -> dict | list:
        return self.query_account_raw({"type": "orderHistory", "user": user})

    def get_fee_tier_raw(self, user: str, symbol: str | None = None) -> dict | list:
        payload = {"type": "feeTier", "user": user}
        if symbol is not None:
            payload["symbol"] = symbol
        return self.query_account_raw(payload)

    def get_open_orders_typed(self, user: str) -> list[OpenOrderItem]:
        data = self.get_open_orders_raw(user)
        if data == []:
            return []

        items = self._unwrap_account_items(data, "openOrder")
        return [
            OpenOrderItem(
                symbol=item["symbol"],
                orderId=item["orderId"],
                price=item["price"],
                originalSize=item["originalSize"],
                size=item["size"],
                filledSize=item["filledSize"],
                vwap=item.get("vwap"),
                maker=item["maker"],
                reduceOnly=item["reduceOnly"],
                orderType=item["orderType"],
                trigger=item.get("trigger"),
                tif=item["tif"],
                status=item["status"],
                timestamp=item["timestamp"],
                raw=item,
            )
            for item in items
        ]

    def get_fills(self, user: str) -> list[FillItem]:
        data = self.get_fills_raw(user)
        if data == []:
            return []

        items = self._unwrap_account_items(data, "fills")
        return [
            FillItem(
                maker=item["maker"],
                taker=item["taker"],
                orderIdMaker=item["orderIdMaker"],
                orderIdTaker=item["orderIdTaker"],
                isBuy=item["isBuy"],
                symbol=item["symbol"],
                amount=item["amount"],
                price=item["price"],
                makerFee=item["makerFee"],
                takerFee=item["takerFee"],
                fee=item["fee"],
                reason=item.get("reason", item.get("reasonCode")),
                slot=item["slot"],
                timestamp=item["timestamp"],
                raw=item,
            )
            for item in items
        ]

    def get_closed_positions(self, user: str) -> list[ClosedPositionItem]:
        data = self.get_positions_raw(user)
        if data == []:
            return []

        items = self._unwrap_account_items(data, "positions")
        return [
            ClosedPositionItem(
                owner=item["owner"],
                symbol=item["symbol"],
                quantity=item.get("quantity"),
                maxQuantity=item["maxQuantity"],
                totalVolume=item["totalVolume"],
                avgOpenPrice=item["avgOpenPrice"],
                avgClosePrice=item["avgClosePrice"],
                realizedPnl=item["realizedPnl"],
                fees=item["fees"],
                funding=item["funding"],
                openTime=item["openTime"],
                closeTime=item["closeTime"],
                closeReason=item["closeReason"],
                raw=item,
            )
            for item in items
        ]

    def get_funding_history(self, user: str) -> list[FundingPaymentItem]:
        data = self.get_funding_history_raw(user)
        if data == []:
            return []

        items = self._unwrap_account_items(data, "fundingPayment")
        return [
            FundingPaymentItem(
                owner=item["owner"],
                symbol=item["symbol"],
                size=item["size"],
                payment=item["payment"],
                fundingRate=item["fundingRate"],
                markPrice=item["markPrice"],
                slot=item["slot"],
                timestamp=item["timestamp"],
                raw=item,
            )
            for item in items
        ]

    def get_order_history(self, user: str) -> list[OrderHistoryItem]:
        data = self.get_order_history_raw(user)
        if data == []:
            return []

        items = self._unwrap_account_items(data, "orderHistory")
        return [
            OrderHistoryItem(
                orderId=item["orderId"],
                symbol=item["symbol"],
                side=item["side"],
                orderType=item["orderType"],
                tif=item["tif"],
                price=item["price"],
                vwap=item.get("vwap"),
                originalSize=item["originalSize"],
                executedSize=item["executedSize"],
                reduceOnly=item["reduceOnly"],
                trigger=item.get("trigger"),
                status=item["status"],
                reason=item.get("reason"),
                slot=item["slot"],
                timestamp=item["timestamp"],
                raw=item,
            )
            for item in items
        ]

    def get_fee_tier(self, user: str, symbol: str | None = None) -> FeeTierState:
        data = self.get_fee_tier_raw(user, symbol)

        items = self._unwrap_account_items(data, "feeTier")
        if len(items) != 1:
            raise BulkAPIError("Unexpected feeTier response shape", raw=data)

        item = items[0]
        return FeeTierState(
            stamp=item["stamp"],
            slot=item["slot"],
            globalPolicyActive=item.get("globalPolicyActive", item.get("global_policy_active", False)),
            instrumentOverridesActive=item.get(
                "instrumentOverridesActive",
                item.get("instrument_overrides_active", 0),
            ),
            scheduledGlobalDepth=item.get("scheduledGlobalDepth", item.get("scheduled_global_depth", 0)),
            scheduledTotalDepth=item.get("scheduledTotalDepth", item.get("scheduled_total_depth", 0)),
            nextActivationSlot=item.get("nextActivationSlot", item.get("next_activation_slot")),
            settledFills=item.get("settledFills", item.get("settled_fills", 0)),
            totalMakerFees=item.get("totalMakerFees", item.get("total_maker_fees", 0.0)),
            totalTakerFees=item.get("totalTakerFees", item.get("total_taker_fees", 0.0)),
            totalProtocolSettlement=item.get(
                "totalProtocolSettlement",
                item.get("total_protocol_settlement", 0.0),
            ),
            scopes=item.get("scopes", []),
            accountQuote=item.get("accountQuote", item.get("account_quote")),
            raw=item,
        )
