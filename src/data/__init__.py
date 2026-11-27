"""Data access layer: fetching from Yahoo Finance and cleaning what comes back.

Import from here rather than from the submodules, so the rest of the project has
one name to reach for::

    from src.data import fetch_ohlcv, clean_ohlcv, DataQualityError
"""

from src.data.cleaner import OHLCV_COLUMNS, DataQualityError, clean_ohlcv
from src.data.fetcher import (
    fetch_company_info,
    fetch_many,
    fetch_ohlcv,
    normalise_ticker,
)

__all__ = [
    "DataQualityError",
    "OHLCV_COLUMNS",
    "clean_ohlcv",
    "fetch_company_info",
    "fetch_many",
    "fetch_ohlcv",
    "normalise_ticker",
]
