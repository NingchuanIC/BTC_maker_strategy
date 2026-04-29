"""Data loading utilities."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator, Optional

import pandas as pd


def load_processed_data(
    data_dir: str, sample_n: Optional[int] = None
) -> pd.DataFrame:
    """
    Load processed CSV files from a directory.
    
    Supports sampling for memory efficiency.
    
    Args:
        data_dir: Directory containing processed CSV files
        sample_n: Number of rows to sample (None for all data)
    
    Returns:
        DataFrame with combined data
    """
    data_dir = Path(data_dir)
    csv_files = sorted(data_dir.glob("*.csv"))

    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")

    if sample_n is None:
        dfs = []
        for csv_file in csv_files:
            df = pd.read_csv(csv_file)
            dfs.append(df)
            print(f"✓ Loaded {csv_file.name}: {len(df)} rows")

        data = pd.concat(dfs, ignore_index=True)
        print(f"\n✓ Total data: {len(data)} rows\n")
        return data

    parts = []
    total = 0
    for csv_file in csv_files:
        if total >= sample_n:
            break

        for chunk in pd.read_csv(csv_file, chunksize=10000):
            need = sample_n - total
            if len(chunk) <= need:
                parts.append(chunk)
                total += len(chunk)
            else:
                parts.append(chunk.iloc[:need])
                total += need

            if total >= sample_n:
                break

        print(f"✓ Read {csv_file.name}, cumulative {total} rows")

    data = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    print(f"\n✓ Sample data: {len(data)} rows\n")
    return data


def load_processed_data_for_date(data_dir: str, date: str) -> pd.DataFrame:
    """Load the processed CSV for a single date."""
    data_dir = Path(data_dir)
    csv_path = data_dir / f"BTC-USDT-SWAP-L2orderbook-400lv-{date}.csv"

    if not csv_path.exists():
        raise FileNotFoundError(f"No CSV file found for date {date}: {csv_path}")

    data = pd.read_csv(csv_path)
    print(f"✓ Loaded {csv_path.name}: {len(data)} rows")
    return data


def iter_dates(start_date: str, end_date: str) -> Iterator[str]:
    """Yield inclusive date strings from start_date to end_date."""
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()

    current = start
    while current <= end:
        yield current.strftime("%Y-%m-%d")
        current += timedelta(days=1)
