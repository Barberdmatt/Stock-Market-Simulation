
import os
from pathlib import Path
from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.data.enums import DataFeed
from datetime import datetime, timedelta, timezone
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit


# Load credentials from the .env file beside this module
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path)

API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

# Our 10 stocks
STOCKS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "META",
    "TSLA",
    "JPM",
    "COST",
    "AMD"
]


def get_market_data():

    if not API_KEY or not SECRET_KEY:
        raise ValueError(
            "Alpaca API keys are missing. Check your .env file."
        )

    # Connect to Alpaca
    client = StockHistoricalDataClient(
        API_KEY,
        SECRET_KEY
    )

    # Request quotes for all 10 stocks
    request = StockLatestQuoteRequest(
        symbol_or_symbols=STOCKS,
        feed=DataFeed.IEX
    )

    quotes = client.get_stock_latest_quote(request)

    results = {}

    for symbol in STOCKS:

        quote = quotes.get(symbol)

        if quote is None:
            print(f"No quote available for {symbol}")
            continue

        bid = quote.bid_price
        ask = quote.ask_price

        mid = (bid + ask) / 2 if bid and ask else None

        results[symbol] = {
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "bid_size": quote.bid_size,
            "ask_size": quote.ask_size,
            "timestamp": quote.timestamp
        }

    return results


def print_market_data():

    data = get_market_data()

    print("\nREAL MARKET DATA")
    print("=" * 75)

    for symbol, quote in data.items():

        print(f"\n{symbol}")
        print(f"  Bid:       ${quote['bid']}")
        print(f"  Ask:       ${quote['ask']}")
        print(f"  Mid-price: ${quote['mid']}")
        print(f"  Bid size:  {quote['bid_size']}")
        print(f"  Ask size:  {quote['ask_size']}")
        print(f"  Timestamp: {quote['timestamp']}")

    print("\n" + "=" * 75)


def get_historical_market_data():

    if not API_KEY or not SECRET_KEY:
        raise ValueError("Alpaca API keys are missing. Check your .env file.")

    client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

    # Request the previous 15 calendar days
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=15)

    request = StockBarsRequest(
        symbol_or_symbols=STOCKS,
        timeframe=TimeFrame(10, TimeFrameUnit.Minute),
        start=start_date,
        end=end_date,
        feed=DataFeed.IEX
    )

    bars = client.get_stock_bars(request).df

    results = {}

    if bars.empty:
        raise ValueError("Alpaca returned no historical stock data.")

    for symbol in STOCKS:

        try:
            stock_bars = bars.xs(symbol, level="symbol")

            results[symbol] = {
                "timestamps": list(stock_bars.index),
                "closes": list(stock_bars["close"])
            }

        except KeyError:
            print(f"No historical data available for {symbol}")

    return results
