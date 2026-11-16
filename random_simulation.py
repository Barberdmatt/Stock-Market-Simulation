
from .model import Params, simulate
from .facts import summary
from .plots import plot_results

def main():
    print("Starting Stock Market Simulation...")

    # Set simulation parameters
    params = Params()

    # Run simulation
    result = simulate(
        p=params,
        n_events=10000,
        seed=42,
        record_messages=True
    )

    print("\nSimulation completed!")

    print("\nMarket Results:")
    print("Number of events:", len(result.t))
    print("Final bid:", result.bid[-1])
    print("Final ask:", result.ask[-1])
    print("Final mid-price:", result.mid[-1])

    # Analyze simulated market behaviour
    results = summary(
        result.t,
        result.bid,
        result.ask,
        result.mo_side,
        result.mo_size,
        result.mo_mid0,
        result.mo_mid1
    )

    plot_results(result)

    print("\nMarket Statistics:")
    for name, value in results.items():
        print(f"{name}: {value}")


if __name__ == "__main__":
    main()
