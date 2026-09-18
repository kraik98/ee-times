from pathlib import Path
from typing import List, Optional, Union

import pandas as pd
import yaml


def generate_timeslices(
    n_seasons: int = 12,
    weekly_labels: Optional[List[str]] = None,
    n_daynite: int = 8,
    year_hours: int = 8760,
) -> dict:
    """
    Generate TIMES-style timeslice labels like:
    S01aH01, S01aH02, ..., S12aH08
    """
    if weekly_labels is None:
        weekly_labels = ["a"]

    seasons = [f"S{i:02d}" for i in range(1, n_seasons + 1)]
    daynites = [f"H{i:02d}" for i in range(1, n_daynite + 1)]

    rows = []
    for s in seasons:
        for w in weekly_labels:
            for h in daynites:
                rows.append(f"{s}{w}{h}")

    n_slices = len(rows)
    avg_hours_per_slice = year_hours / n_slices

    return {
        "timeslices": rows,
        "n_seasons": n_seasons,
        "n_weekly": len(weekly_labels),
        "n_daynite": n_daynite,
        "n_slices": n_slices,
        "year_hours": year_hours,
        "avg_hours_per_slice": avg_hours_per_slice,
    }


def assign_timeslice(
    ts: pd.Timestamp,
    n_seasons: int,
    n_daynite: int,
    weekly_labels: Optional[List[str]] = None,
) -> str:
    if weekly_labels is None:
        weekly_labels = ["a"]

    season = (ts.month - 1) * n_seasons // 12 + 1
    daynite = ts.hour * n_daynite // 24 + 1
    weekly = weekly_labels[0]
    return f"S{season:02d}{weekly}H{daynite:02d}"


def load_config(config_path: Union[str, Path]) -> dict:
    config_path = Path(config_path).resolve()
    with config_path.open(encoding="utf-8") as f:
        config = yaml.safe_load(f)
    config["_config_dir"] = config_path.parent
    return config


def _resolve_path(config: dict, relative_path: str) -> Path:
    return (config["_config_dir"] / relative_path).resolve()


def _read_input_dataframe(config: dict) -> pd.DataFrame:
    input_cfg = config["input"]
    input_path = _resolve_path(config, input_cfg["file"])

    if input_path.suffix.lower() == ".csv":
        return pd.read_csv(input_path)

    return pd.read_excel(input_path, sheet_name=input_cfg.get("sheet_name", 0))


def aggregate_hourly_to_timeslices(config: dict) -> pd.DataFrame:
    input_cfg = config["input"]
    ts_cfg = config["timeslices"]
    output_cfg = config["output"]

    n_seasons = ts_cfg["n_seasons"]
    n_daynite = ts_cfg["n_daynite"]
    weekly_labels = ts_cfg.get("weekly_labels", ["a"])
    year_hours = ts_cfg.get("year_hours", 8760)
    aggregation = output_cfg.get("aggregation", "mean").lower()

    timestamp_col = input_cfg["timestamp_col"]
    value_col = input_cfg["value_col"]
    output_path = _resolve_path(config, output_cfg["file"])

    df = _read_input_dataframe(config)
    df[timestamp_col] = pd.to_datetime(df[timestamp_col], utc=True)
    df["timeslice"] = df[timestamp_col].apply(
        lambda ts: assign_timeslice(ts, n_seasons, n_daynite, weekly_labels)
    )

    aggregated = (
        df.groupby("timeslice", as_index=False)
        .agg(
            hours=(value_col, "size"),
            value_sum=(value_col, "sum"),
            value_avg=(value_col, "mean"),
        )
    )

    ts_result = generate_timeslices(n_seasons, weekly_labels, n_daynite, year_hours)
    full_timeslices = pd.DataFrame({"timeslice": ts_result["timeslices"]})
    aggregated = full_timeslices.merge(aggregated, on="timeslice", how="left")
    aggregated["hours"] = aggregated["hours"].fillna(0).astype(int)
    aggregated["value_sum"] = aggregated["value_sum"].fillna(0.0)
    aggregated["value_avg"] = aggregated["value_avg"].fillna(0.0)

    aggregated["season"] = aggregated["timeslice"].str[:3]
    aggregated["weekly"] = aggregated["timeslice"].str[3:4]
    aggregated["daynite"] = aggregated["timeslice"].str[4:]

    if aggregation == "sum":
        copy_values = aggregated["value_sum"]
    elif aggregation == "mean":
        copy_values = aggregated["value_avg"]
    else:
        raise ValueError(f"Unsupported aggregation: {aggregation!r}. Use 'mean' or 'sum'.")

    copy_df = pd.DataFrame({"timeslice": aggregated["timeslice"], "value": copy_values})

    hourly_out = df.copy()
    hourly_out[timestamp_col] = hourly_out[timestamp_col].dt.strftime("%Y-%m-%d %H:%M:%S")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        copy_df.to_excel(writer, sheet_name="copy", index=False)
        aggregated.to_excel(writer, sheet_name="aggregated", index=False)
        hourly_out.to_excel(writer, sheet_name="hourly_with_timeslice", index=False)

    config["_summary"] = {
        **ts_result,
        "output_file": str(output_path),
        "aggregation": aggregation,
        "value_col": value_col,
    }
    return aggregated


def print_summary(config: dict):
    summary = config["_summary"]
    print(f"Seasons: {summary['n_seasons']}")
    print(f"Weekly categories: {summary['n_weekly']}")
    print(f"Daynite categories: {summary['n_daynite']}")
    print(f"Total timeslices: {summary['n_slices']}")
    print(f"Total year hours represented: {summary['year_hours']}")
    print(f"Average hours per slice: {summary['avg_hours_per_slice']:.2f}")
    print(f"Aggregation: {summary['aggregation']}")
    print(f"Value column: {summary['value_col']}")
    print(f"Output file: {summary['output_file']}")
