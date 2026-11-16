
from .market_data import (
    get_market_data,
    get_historical_market_data
)

from .plots import plot_live_market_prices


if __name__ == "__main__":

    print("Starting Live Stock Market Dashboard...")
    print("Loading historical data...")
    print("Tracking 10 companies.")
    print("Live updates every 5 seconds.")
    print("Close the graph window to stop.")

    plot_live_market_prices(
        get_market_data,
        get_historical_market_data,
        interval=5000
    )
