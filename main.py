import subprocess
import sys
from pathlib import Path
from .portfolio import run_portfolio

# The folder containing the Stock_Market_Simulation package
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def show_menu():

    while True:

        print("\n" + "=" * 45)
        print("       STOCK MARKET SIMULATION")
        print("=" * 45)

        print("\n1. Random Market Simulation")
        print("2. Real Market Dashboard")
        print("3. Paper Trading Portfolio")
        print("4. Exit")

        choice = input("\nSelect an option (1-4): ").strip()

        if choice == "1":

            print("\nStarting Random Market Simulation...\n")

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "Stock_Market_Simulation.random_simulation"
                ],
                cwd=PROJECT_ROOT
            )

        elif choice == "2":

            print("\nStarting Real Market Dashboard...\n")

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "Stock_Market_Simulation.test_market_data"
                ],
                cwd=PROJECT_ROOT
            )

        elif choice == "3":

            run_portfolio()

        elif choice == "4":

            print("\nExiting Stock Market Simulation.")
            break

        else:

            print("\nInvalid option. Please enter 1, 2, 3, or 4")


if __name__ == "__main__":
    show_menu()
