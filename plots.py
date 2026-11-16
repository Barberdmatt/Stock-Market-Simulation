
import numpy as np
import matplotlib.pyplot as plt


def plot_results(result):

    # Chart 1: Mid-price over time
    plt.figure(figsize=(10, 5))
    plt.plot(result.t, result.mid)

    plt.title("Stock Mid-Price Over Time")
    plt.xlabel("Time")
    plt.ylabel("Mid-Price")
    plt.grid(True)

    # Chart 2: Bid-Ask Spread over time
    spread = result.ask - result.bid

    plt.figure(figsize=(10, 5))
    plt.plot(result.t, spread)

    plt.title("Bid-Ask Spread Over Time")
    plt.xlabel("Time")
    plt.ylabel("Spread")
    plt.grid(True)

    # Chart 3: Order Book Depth
    plt.figure(figsize=(10, 5))

    levels = range(result.depth.shape[1])

    plt.plot(levels, result.depth[0], label="Buy Orders")
    plt.plot(levels, result.depth[1], label="Sell Orders")

    plt.title("Order Book Depth")
    plt.xlabel("Price Level")
    plt.ylabel("Order Quantity")
    plt.legend()
    plt.grid(True)

    # Display all charts
    plt.show()


def plot_market_overview(data):

    import matplotlib.pyplot as plt

    # Remove stocks without valid quotes
    stocks = {
        symbol: quote
        for symbol, quote in data.items()
        if quote["mid"] is not None
    }

    symbols = list(stocks.keys())

    mid_prices = [
        stocks[symbol]["mid"]
        for symbol in symbols
    ]

    spreads = [
        stocks[symbol]["ask"] - stocks[symbol]["bid"]
        for symbol in symbols
    ]

    # Chart 1: Stock mid-prices
    plt.figure(figsize=(12, 6))

    plt.bar(symbols, mid_prices)

    plt.title("Real Market - Stock Mid-Prices")
    plt.xlabel("Stock")
    plt.ylabel("Price ($)")
    plt.grid(axis="y")

    plt.tight_layout()

    # Chart 2: Bid-ask spreads
    plt.figure(figsize=(12, 6))

    plt.bar(symbols, spreads)

    plt.title("Real Market - Bid-Ask Spreads")
    plt.xlabel("Stock")
    plt.ylabel("Spread ($)")
    plt.grid(axis="y")

    plt.tight_layout()
    plt.show()



def plot_live_market_prices(
    get_market_data,
    get_historical_market_data,
    interval=5000
):

    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.animation import FuncAnimation
    from datetime import datetime, timezone

    stocks = [
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL",
        "META", "TSLA", "JPM", "COST", "AMD"
    ]

    print("Loading previous 15 days of stock prices...")

    # Download historical data before opening the graph
    historical = get_historical_market_data()

    history = {}
    starting_prices = {}

    for symbol in stocks:

        stock_data = historical.get(symbol)

        if not stock_data or not stock_data["closes"]:
            continue

        timestamps = stock_data["timestamps"]
        closes = stock_data["closes"]

        starting_prices[symbol] = float(closes[0])

        # Convert historical prices to percentage changes
        percentages = [
            ((float(price) / starting_prices[symbol]) - 1) * 100
            for price in closes
        ]

        history[symbol] = {
            "timestamps": list(timestamps),
            "prices": percentages
        }

    fig, ax = plt.subplots(figsize=(14, 8))

    lines = {}

    # Draw the historical lines immediately
    for symbol in stocks:

        if symbol not in history:
            continue

        line, = ax.plot(
            history[symbol]["timestamps"],
            history[symbol]["prices"],
            label=symbol,
            linewidth=2
        )

        lines[symbol] = line

    ax.set_title("Stock Market - 30 Days of History + Live Prices")
    ax.set_xlabel("Date and Time")
    ax.set_ylabel("Change from Starting Price (%)")

    ax.legend(loc="upper left", ncol=2)
    ax.grid(True, alpha=0.3)

    ax.xaxis.set_major_formatter(
        mdates.DateFormatter("%b %d")
    )

    fig.autofmt_xdate()

    def update(frame):

        data = get_market_data()
        current_time = datetime.now(timezone.utc)

        for symbol in stocks:

            quote = data.get(symbol)

            if quote is None or quote["mid"] is None:
                continue

            current_price = float(quote["mid"])

            if symbol not in starting_prices:
                starting_prices[symbol] = current_price

            if symbol not in history:

                history[symbol] = {
                    "timestamps": [],
                    "prices": []
                }

            percentage_change = (
                (current_price / starting_prices[symbol]) - 1
            ) * 100

            history[symbol]["timestamps"].append(current_time)
            history[symbol]["prices"].append(percentage_change)

            if symbol not in lines:

                line, = ax.plot(
                    history[symbol]["timestamps"],
                    history[symbol]["prices"],
                    label=symbol,
                    linewidth=2
                )

                lines[symbol] = line
                ax.legend(loc="upper left", ncol=2)

            else:

                lines[symbol].set_data(
                    history[symbol]["timestamps"],
                    history[symbol]["prices"]
                )

        ax.relim()
        ax.autoscale_view()

        return list(lines.values())

    animation = FuncAnimation(
        fig,
        update,
        interval=interval,
        blit=False,
        cache_frame_data=False
    )

    plt.tight_layout()
    plt.show()
