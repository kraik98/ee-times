import argparse
from pathlib import Path

from timeslices import aggregate_hourly_to_timeslices, load_config, print_summary


def main():
    parser = argparse.ArgumentParser(description="Aggregate hourly data to TIMES timeslices.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).parent / "config.yaml",
        help="Path to YAML config file (default: config.yaml next to this script)",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    aggregate_hourly_to_timeslices(config)
    print_summary(config)


if __name__ == "__main__":
    main()
