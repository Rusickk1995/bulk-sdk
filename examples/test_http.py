from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bulk_sdk import BulkClient


def main() -> None:
    with BulkClient() as client:
        markets = client.get_markets()
        print("MARKETS COUNT:", len(markets))
        print("FIRST MARKET:", markets[0])

        ticker = client.get_ticker("BTC-USD")
        print("TICKER BTC-USD:", ticker)

        book = client.get_order_book("BTC-USD", nlevels=5)
        print("BEST BID:", book.best_bid())
        print("BEST ASK:", book.best_ask())
        print("SPREAD:", book.spread())
        print("BOOK TIMESTAMP:", book.timestamp)

        candles = client.get_candles("BTC-USD", "1m")
        print("CANDLES COUNT:", len(candles))
        print("LAST CANDLE:", candles[-1])

        stats = client.get_stats(symbol="BTC-USD", period="1d")
        print("STATS PERIOD:", stats.period)
        print("STATS MARKETS COUNT:", len(stats.markets))
        print("STATS FIRST MARKET:", stats.markets[0] if stats.markets else None)

        risk_surfaces = client.get_risk_surfaces("BTC-USD")
        print("RISK SURFACES SYMBOL:", risk_surfaces.symbol)
        print("RISK LIVE REGIME:", risk_surfaces.liveRegime)
        print("RISK SURFACES COUNT:", len(risk_surfaces.surfaces))

        fee_state = client.get_fee_state()
        print("FEE STATE STAMP:", fee_state.stamp)
        print("FEE STATE SLOT:", fee_state.slot)
        print("FEE SCOPES COUNT:", len(fee_state.scopes))


if __name__ == "__main__":
    main()
