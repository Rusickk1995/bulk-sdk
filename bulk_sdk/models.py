"""Dataclass models for BULK Exchange HTTP market data."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Market:
    symbol: str
    baseAsset: str
    quoteAsset: str
    status: str
    pricePrecision: int
    sizePrecision: int
    tickSize: float
    lotSize: float
    minNotional: float
    maxLeverage: int
    orderTypes: list[str] = field(default_factory=list)
    timeInForces: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class Ticker:
    symbol: str
    priceChange: float
    priceChangePercent: float
    lastPrice: float
    highPrice: float
    lowPrice: float
    volume: float
    quoteVolume: float
    markPrice: float
    oraclePrice: float
    openInterest: float
    fundingRate: float
    regime: int
    regimeDt: int
    regimeVol: float
    regimeMv: float
    fairBookPx: float
    fairVol: float
    fairBias: float
    timestamp: int
    raw: dict = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class OrderBookLevel:
    px: float
    sz: float
    n: int
    raw: dict = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class OrderBook:
    updateType: str
    symbol: str
    levels: list[list[OrderBookLevel]] = field(default_factory=lambda: [[], []])
    timestamp: int | None = None
    raw: dict = field(default_factory=dict, repr=False)

    def best_bid(self) -> OrderBookLevel | None:
        bids = self.levels[0] if len(self.levels) > 0 else []
        return max(bids, key=lambda level: level.px, default=None)

    def best_ask(self) -> OrderBookLevel | None:
        asks = self.levels[1] if len(self.levels) > 1 else []
        return min(asks, key=lambda level: level.px, default=None)

    def spread(self) -> float | None:
        bid = self.best_bid()
        ask = self.best_ask()

        if bid is None or ask is None:
            return None

        return ask.px - bid.px


@dataclass(slots=True)
class Candle:
    t: int
    T: int
    o: float
    h: float
    l: float
    c: float
    v: float
    n: int
    raw: dict = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class ExchangeStats:
    timestamp: int
    period: str
    volume: dict = field(default_factory=dict)
    openInterest: dict = field(default_factory=dict)
    funding: dict = field(default_factory=dict)
    markets: list[dict] = field(default_factory=list)
    raw: dict = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class RiskSurfaces:
    symbol: str
    liveRegime: int
    surfaces: list[dict] = field(default_factory=list)
    corrs: list[list[object]] = field(default_factory=list)
    raw: dict = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class FeeState:
    stamp: int
    slot: int
    trackable_id: dict = field(default_factory=dict)
    global_policy_active: bool = False
    instrument_overrides_active: int = 0
    scheduled_global_depth: int = 0
    scheduled_total_depth: int = 0
    next_activation_slot: int | None = None
    settled_fills: int = 0
    total_maker_fees: float = 0.0
    total_taker_fees: float = 0.0
    total_protocol_settlement: float = 0.0
    scopes: list[dict] = field(default_factory=list)
    raw: dict = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class Margin:
    totalBalance: float
    availableBalance: float
    marginUsed: float
    notional: float
    realizedPnl: float
    unrealizedPnl: float
    fees: float
    funding: float
    raw: dict = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class Position:
    symbol: str
    size: float
    price: float
    fairPrice: float
    notional: float
    realizedPnl: float
    unrealizedPnl: float
    leverage: float
    liquidationPrice: float
    fees: float
    funding: float
    maintenanceMargin: float
    lambda_: float
    riskAllocation: float
    raw: dict = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class OpenOrder:
    raw: dict = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class FeeTier:
    symbol: str
    rollingVolume: float
    tierIndex: int
    tierThreshold: float
    makerBps: float
    takerBps: float
    windowDays: int
    raw: dict = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class LeverageSetting:
    symbol: str
    leverage: float
    raw: dict = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class AccountState:
    margin: Margin
    positions: list[Position] = field(default_factory=list)
    openOrders: list[OpenOrder] = field(default_factory=list)
    feeTiers: list[FeeTier] = field(default_factory=list)
    leverageSettings: list[LeverageSetting] = field(default_factory=list)
    raw: dict = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class OpenOrderItem:
    symbol: str
    orderId: str
    price: float
    originalSize: float
    size: float
    filledSize: float
    vwap: float | None
    maker: bool
    reduceOnly: bool
    orderType: str
    trigger: dict | None
    tif: str
    status: str
    timestamp: int
    raw: dict = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class FillItem:
    maker: str
    taker: str
    orderIdMaker: str
    orderIdTaker: str
    isBuy: bool
    symbol: str
    amount: float
    price: float
    makerFee: float
    takerFee: float
    fee: float
    reason: str | int | None
    slot: int
    timestamp: int
    raw: dict = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class ClosedPositionItem:
    owner: str
    symbol: str
    quantity: float | None
    maxQuantity: float
    totalVolume: float
    avgOpenPrice: float
    avgClosePrice: float
    realizedPnl: float
    fees: float
    funding: float
    openTime: int
    closeTime: int
    closeReason: str
    raw: dict = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class FundingPaymentItem:
    owner: str
    symbol: str
    size: float
    payment: float
    fundingRate: float
    markPrice: float
    slot: int
    timestamp: int
    raw: dict = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class OrderHistoryItem:
    orderId: str
    symbol: str
    side: str
    orderType: str
    tif: str
    price: float
    vwap: float | None
    originalSize: float
    executedSize: float
    reduceOnly: bool
    trigger: dict | None
    status: str
    reason: str | int | None
    slot: int
    timestamp: int
    raw: dict = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class FeeTierState:
    stamp: int
    slot: int
    globalPolicyActive: bool
    instrumentOverridesActive: int
    scheduledGlobalDepth: int
    scheduledTotalDepth: int
    nextActivationSlot: int | None
    settledFills: int
    totalMakerFees: float
    totalTakerFees: float
    totalProtocolSettlement: float
    scopes: list | dict
    accountQuote: dict | None
    raw: dict = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class OrderStatusEntry:
    raw: dict = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class OrderResponseData:
    statuses: list[dict] = field(default_factory=list)
    raw: dict = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class OrderResponse:
    top_level_status: str
    response_type: str | None = None
    statuses: list[dict] = field(default_factory=list)
    raw: dict = field(default_factory=dict, repr=False)
