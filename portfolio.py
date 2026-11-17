import json
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone


# Starting virtual cash
STARTING_CASH = 100000.00

# Save portfolio data beside this file
PORTFOLIO_FILE = Path(__file__).resolve().parent / "portfolio.json"


class Portfolio:

    def __init__(self, path=PORTFOLIO_FILE):

        self.path = Path(path)
        self.cash = STARTING_CASH
        self.positions = {}
        self.realized_profit = 0.0
        self.history = []
        self.trades = []
        self.load()

    def load(self):

        if not self.path.exists():
            return

        try:
            with open(self.path, "r") as file:
                data = json.load(file)

            self.cash = float(data.get("cash", STARTING_CASH))
            self.positions = data.get("positions", {})
            self.realized_profit = float(
                data.get("realized_profit", 0.0)
            )
            self.history = data.get("history", [])
            self.trades = data.get("trades", [])

        except (OSError, ValueError, TypeError):
            print("Could not load portfolio. Starting a new one.")

    def save(self):

        data = {
            "cash": self.cash,
            "positions": self.positions,
            "realized_profit": self.realized_profit,
            "history": self.history,
            "trades": self.trades
        }

        with open(self.path, "w") as file:
            json.dump(data, file, indent=4)


    def record_snapshot(self, market_data):

        stock_values = {}
        total_stock_value = 0.0

        for symbol, position in self.positions.items():

            quote = market_data.get(symbol)

            if not quote or quote["mid"] is None:
                continue

            current_price = float(quote["mid"])
            value = position["quantity"] * current_price

            stock_values[symbol] = value
            total_stock_value += value

        total_value = self.cash + total_stock_value

        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_value": total_value,
            "cash": self.cash,
            "stock_values": stock_values
        }

        self.history.append(snapshot)

        # Keep the most recent year of snapshots
        self.history = self.history[-10000:]

        self.save()

        return snapshot


    def apply_fill(self, symbol, is_buy, quantity, price, kind="Market"):
        """Record a trade the exchange has already executed (the server checks funds first)."""
        profit = None
        if is_buy:
            old = self.positions.get(symbol, {"quantity": 0, "avg_cost": 0.0})
            new_q = old["quantity"] + quantity
            self.positions[symbol] = {
                "quantity": new_q,
                "avg_cost": (old["avg_cost"] * old["quantity"] + price * quantity) / new_q,
            }
            self.cash -= price * quantity
        else:
            pos = self.positions[symbol]
            profit = quantity * (price - pos["avg_cost"])
            pos["quantity"] -= quantity
            self.cash += price * quantity
            self.realized_profit += profit
            if pos["quantity"] == 0:
                del self.positions[symbol]
        self.trades.insert(0, {"t": int(time.time() * 1000), "s": symbol,
                               "sd": "b" if is_buy else "s", "q": quantity,
                               "px": price, "type": kind, "pl": profit})
        del self.trades[500:]
        self.save()

    def buy(self, symbol, quantity, price):
        if quantity * price > self.cash:
            return False, "Not enough cash for this purchase."
        self.apply_fill(symbol, True, quantity, price)
        return True, f"Bought {quantity} shares of {symbol} at ${price:.2f} each."

    def sell(self, symbol, quantity, price):
        position = self.positions.get(symbol)
        if position is None or quantity > position["quantity"]:
            return False, "You do not own enough shares to sell."
        profit = quantity * (price - position["avg_cost"])
        self.apply_fill(symbol, False, quantity, price)
        return True, (f"Sold {quantity} shares of {symbol} at ${price:.2f} each.\n"
                      f"Realized profit/loss: ${profit:,.2f}")
    
    def show_portfolio(self, market_data):

        market_value = 0.0
        unrealized_profit = 0.0

        print("\n" + "=" * 75)
        print("                    YOUR PORTFOLIO")
        print("=" * 75)

        print(f"Available cash: ${self.cash:,.2f}")

        print("\nYOUR STOCK HOLDINGS")
        print("-" * 75)

        if not self.positions:
            print("You do not own any shares yet.")

        else:
            print(
                f"{'Stock':<10}"
                f"{'Shares':<10}"
                f"{'Avg Cost':<14}"
                f"{'Price':<14}"
                f"{'Market Value':<16}"
                f"{'Profit/Loss':<14}"
            )

            for symbol, position in self.positions.items():

                quote = market_data.get(symbol)

                if not quote or quote["mid"] is None:
                    print(f"{symbol:<10} Current quote unavailable")
                    continue

                quantity = position["quantity"]
                average_cost = position["avg_cost"]
                current_price = float(quote["mid"])

                value = quantity * current_price
                profit = quantity * (current_price - average_cost)

                market_value += value
                unrealized_profit += profit

                print(
                    f"{symbol:<10}"
                    f"{quantity:<10}"
                    f"${average_cost:<13.2f}"
                    f"${current_price:<13.2f}"
                    f"${value:<15.2f}"
                    f"${profit:,.2f}"
                )

        total_value = self.cash + market_value

        print("\n" + "-" * 75)
        print(f"Stock market value:       ${market_value:,.2f}")
        print(f"Available cash:           ${self.cash:,.2f}")
        print(f"Total portfolio value:    ${total_value:,.2f}")
        print(f"Realized profit/loss:     ${self.realized_profit:,.2f}")
        print(f"Unrealized profit/loss:   ${unrealized_profit:,.2f}")
        print(
            f"Total profit/loss:        "
            f"${self.realized_profit + unrealized_profit:,.2f}"
        )
        print("=" * 75)

    
    def show_performance_dashboard(self, market_data):

        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

        # Save a new account-value snapshot
        self.record_snapshot(market_data)

        # Calculate current holdings and performance
        stock_values = {}
        stock_profits = {}

        for symbol, position in self.positions.items():

            quote = market_data.get(symbol)

            if not quote or quote["mid"] is None:
                continue

            current_price = float(quote["mid"])
            quantity = position["quantity"]
            average_cost = position["avg_cost"]

            stock_values[symbol] = quantity * current_price
            stock_profits[symbol] = (
                quantity * (current_price - average_cost)
            )

        stock_value = sum(stock_values.values())
        total_value = self.cash + stock_value

        total_profit = total_value - STARTING_CASH
        total_return = (total_profit / STARTING_CASH) * 100

        # Calculate daily profit/loss when 24-hour history exists
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=24)

        previous_snapshot = None

        for snapshot in self.history[:-1]:

            snapshot_time = datetime.fromisoformat(
                snapshot["timestamp"]
            )

            if snapshot_time <= cutoff:
                previous_snapshot = snapshot

        print("\n" + "=" * 60)
        print("             PORTFOLIO PERFORMANCE")
        print("=" * 60)

        print(f"Total portfolio value: ${total_value:,.2f}")
        print(f"Total profit/loss:     ${total_profit:,.2f}")
        print(f"Total return:          {total_return:.2f}%")

        if previous_snapshot is not None:

            daily_profit = (
                total_value - previous_snapshot["total_value"]
            )

            daily_return = (
                daily_profit / previous_snapshot["total_value"]
            ) * 100

            print(f"24-hour profit/loss:   ${daily_profit:,.2f}")
            print(f"24-hour return:        {daily_return:.2f}%")

        else:

            print("24-hour profit/loss:   Collecting history...")
            print("A full 24 hours of snapshots is needed.")

        print("=" * 60)

        # Prepare portfolio history for the line graph
        dates = [
            datetime.fromisoformat(item["timestamp"])
            for item in self.history
        ]

        values = [
            item["total_value"]
            for item in self.history
        ]

        # Create a four-part dashboard
        fig, axes = plt.subplots(2, 2, figsize=(14, 9))

        fig.suptitle(
            "Stock Market Simulator - Portfolio Dashboard",
            fontsize=16,
            fontweight="bold"
        )

        # Graph 1: Total portfolio value over time
        ax = axes[0, 0]

        ax.plot(dates, values, linewidth=2, marker="o")
        ax.axhline(
            STARTING_CASH,
            linestyle="--",
            label="Starting balance"
        )

        ax.set_title("Portfolio Value Over Time")
        ax.set_ylabel("Account Value ($)")
        ax.xaxis.set_major_formatter(
            mdates.DateFormatter("%m/%d %H:%M")
        )
        ax.tick_params(axis="x", rotation=25)
        ax.grid(True, alpha=0.3)
        ax.legend()

        # Graph 2: Current value of each stock
        ax = axes[0, 1]

        if stock_values:

            symbols = list(stock_values.keys())
            market_values = list(stock_values.values())

            ax.bar(symbols, market_values)
            ax.set_title("Current Investment Values")
            ax.set_ylabel("Market Value ($)")
            ax.tick_params(axis="x", rotation=30)
            ax.grid(axis="y", alpha=0.3)

        else:
            ax.text(
                0.5, 0.5, "No stock holdings",
                ha="center", va="center"
            )
            ax.set_title("Current Investment Values")

        # Graph 3: Portfolio allocation, including cash
        ax = axes[1, 0]

        allocation_labels = []
        allocation_values = []

        if self.cash > 0:
            allocation_labels.append("Cash")
            allocation_values.append(self.cash)

        for symbol, value in stock_values.items():
            if value > 0:
                allocation_labels.append(symbol)
                allocation_values.append(value)

        if allocation_values:

            ax.pie(
                allocation_values,
                labels=allocation_labels,
                autopct="%1.1f%%",
                startangle=90
            )

            ax.set_title("Portfolio Allocation")

        else:
            ax.text(
                0.5, 0.5, "No portfolio value",
                ha="center", va="center"
            )
            ax.set_title("Portfolio Allocation")

        # Graph 4: Profit/loss for each stock
        ax = axes[1, 1]

        if stock_profits:

            symbols = list(stock_profits.keys())
            profits = list(stock_profits.values())

            ax.bar(symbols, profits)
            ax.axhline(0, linewidth=1)

            ax.set_title("Unrealized Profit / Loss by Stock")
            ax.set_ylabel("Profit / Loss ($)")
            ax.tick_params(axis="x", rotation=30)
            ax.grid(axis="y", alpha=0.3)

        else:
            ax.text(
                0.5, 0.5, "No stock holdings",
                ha="center", va="center"
            )
            ax.set_title("Unrealized Profit / Loss by Stock")

        plt.tight_layout()
        plt.show()



def run_portfolio():
    from .market_data import STOCKS, get_market_data
    portfolio = Portfolio()

    while True:

        print("\n" + "=" * 45)
        print("             PAPER TRADING")
        print("=" * 45)

        print(f"Available cash: ${portfolio.cash:,.2f}")
        print("\n1. Buy shares")
        print("2. Sell shares")
        print("3. View portfolio")
        print("4. View stock prices")
        print("5. Performance dashboard")
        print("6. Return to main menu")

        choice = input("\nSelect an option (1-6): ").strip()

        if choice == "6":
            break

        if choice not in ("1", "2", "3", "4", "5"):
            print("Invalid selection.")
            continue

        try:
            market_data = get_market_data()
        except Exception as error:
            print(f"Could not retrieve market data: {error}")
            continue

        if choice == "3":
            portfolio.show_portfolio(market_data)

        elif choice == "4":

            print("\nLATEST STOCK PRICES")
            print("-" * 40)

            for symbol in STOCKS:
                quote = market_data.get(symbol)

                if quote and quote["mid"] is not None:
                    print(f"{symbol:<8} ${float(quote['mid']):,.2f}")
                else:
                    print(f"{symbol:<8} Quote unavailable")

        elif choice == "5":

            portfolio.show_performance_dashboard(market_data)

        elif choice in ("1", "2"):

            symbol = input(
                "Enter stock symbol (e.g. AAPL): "
            ).strip().upper()

            if symbol not in STOCKS:
                print("That stock is not in your supported stock list.")
                continue

            quote = market_data.get(symbol)

            if not quote or quote["mid"] is None:
                print("A valid quote is not available for this stock.")
                continue

            price = float(quote["mid"])

            print(f"\n{symbol} current mid-price: ${price:.2f}")

            try:
                quantity = int(input("Number of shares: "))

                if quantity <= 0:
                    print("Quantity must be greater than zero.")
                    continue

            except ValueError:
                print("Please enter a whole number of shares.")
                continue

            ok, message = (portfolio.buy if choice == "1" else portfolio.sell)(symbol, quantity, price)
            print(message)

    print("\nReturning to the main menu...")
