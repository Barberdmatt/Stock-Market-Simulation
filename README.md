# Stock Market Simulation

A Python-based stock market simulation that combines a simulated limit order book with real-world stock market data. The project features live stock price visualizations, paper trading, portfolio management, and performance tracking.

## Features

### 1. Random Market Simulation
- Event-driven limit order book simulation.
- Simulates buying and selling activity.
- Tracks bid prices, ask prices, and market movements.
- Calculates market statistics and stylized financial facts.

### 2. Real-Time Stock Market Dashboard
- Retrieves real stock market quotes using the Alpaca Markets API.
- Tracks 10 publicly traded companies:
  - Apple (AAPL)
  - Microsoft (MSFT)
  - NVIDIA (NVDA)
  - Amazon (AMZN)
  - Alphabet (GOOGL)
  - Meta (META)
  - Tesla (TSLA)
  - JPMorgan Chase (JPM)
  - Costco (COST)
  - AMD (AMD)
- Displays historical and live stock prices using Matplotlib.
- Updates the dashboard automatically every 5 seconds.
- Displays percentage price changes over time.

### 3. Paper Trading System
- Starts with a virtual balance of $100,000.
- Buy and sell shares using simulated trades.
- Tracks cash balances and stock holdings.
- Calculates realized and unrealized profit and loss.
- Saves portfolio information between sessions.

### 4. Portfolio Performance Dashboard
- Displays total portfolio value over time.
- Visualizes investment values for individual stocks.
- Shows portfolio allocation.
- Tracks unrealized profit and loss by stock.
- Provides portfolio performance statistics.

## Technologies Used

- Python 3.12
- NumPy
- Pandas
- Matplotlib
- Alpaca Markets API
- alpaca-py
- python-dotenv
- Git and GitHub

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Barberdmatt/Stock-Market-Simulation.git
```

### 2. Navigate into the project directory

```bash
cd Stock-Market-Simulation
```

### 3. Install dependencies

```bash
py -3.12 -m pip install numpy pandas matplotlib alpaca-py python-dotenv
```

### 4. Configure Alpaca API credentials

Create a free account at [Alpaca Markets](https://alpaca.markets/) and generate your API credentials.

Create a file named `.env` inside the `Stock_Market_Simulation` package folder.

Add your credentials:

```text
ALPACA_API_KEY=your_api_key
ALPACA_SECRET_KEY=your_secret_key
```

**Important:** Never upload your `.env` file or share your API credentials publicly.

## Running the Project

From the repository's parent directory, run:

```bash
py -3.12 -m Stock_Market_Simulation.main
```

The main menu provides the following options:

1. Random Market Simulation
2. Real Market Dashboard
3. Portfolio Trading System
4. Exit

The portfolio menu provides options for buying and selling shares, viewing holdings, checking stock prices, and viewing portfolio performance.

## Project Structure

```text
Stock-Market-Simulation/
│
├── Stock_Market_Simulation/
│   ├── __init__.py
│   ├── main.py
│   ├── random_simulation.py
│   ├── book.py
│   ├── model.py
│   ├── facts.py
│   ├── market_data.py
│   ├── plots.py
│   ├── portfolio.py
│   ├── test_market_data.py
│   ├── .env
│   └── portfolio.json
│
├── .gitignore
└── README.md
```

The `.env` and `portfolio.json` files are local configuration and data files and should not be committed to GitHub.

## Notes

- Real market data is retrieved through Alpaca's IEX data feed.
- Market data availability depends on the API account and data feed.
- The trading system is a paper trading simulation. It does not submit real brokerage orders.
- Simulated trades use the quoted midpoint price and do not currently account for commissions or slippage.
- Historical stock data is used to initialize the live price charts.

## Author

**Matthew Barber**

GitHub: [@Barberdmatt](https://github.com/Barberdmatt)