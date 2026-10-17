"""Shared helpers for locating the input data of the experiments.

The sentiment CSVs are not versioned. They are looked up in, by priority:

1. the directory named by the ``TRADING_DATA_DIR`` environment variable,
2. the ``data/`` directory at the root of this repository.

Each CSV is addressed by name without extension, e.g. ``csv_path("AAPL")``
resolves to ``<data dir>/AAPL.csv``.
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("TRADING_DATA_DIR", REPO_ROOT / "data"))


def csv_path(name):
    """Return the path of ``<data dir>/<name>.csv`` or raise a helpful error."""
    path = DATA_DIR / f"{name}.csv"
    if not path.is_file():
        raise FileNotFoundError(
            f"Input data not found: {path}\n"
            "Place the CSV there or set the TRADING_DATA_DIR environment variable "
            "(see the 'Data' section of the README)."
        )
    return path


# Fraction of the history used to fit/optimize parameters. The rest is held out.
TRAIN_FRACTION = 0.25


def split_train_test(df):
    """Chronological split: first ``TRAIN_FRACTION`` of the rows vs the rest."""
    train_size = int(len(df) * TRAIN_FRACTION)
    return df.iloc[:train_size], df.iloc[train_size:]


def select_window(df, window):
    """Return the part of ``df`` a backtest should run on.

    ``"test"``  held-out (out-of-sample) rows - the default for evaluation,
    ``"train"`` the rows used for optimization,
    ``"full"``  everything (in-sample for the train part; use with care).
    """
    if window == "full":
        return df
    train, test = split_train_test(df)
    if window == "train":
        return train
    if window == "test":
        return test
    raise ValueError(f"window must be 'train', 'test' or 'full', got {window!r}")
