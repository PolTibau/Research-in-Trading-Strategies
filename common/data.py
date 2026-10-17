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
