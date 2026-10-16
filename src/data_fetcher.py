"""Abruf von OHLCV-Kursdaten über yfinance."""
from __future__ import annotations

import datetime as dt
import logging

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def fetch_daily(ticker: str, lookback_days: int) -> pd.DataFrame:
    end = dt.datetime.now(dt.timezone.utc)
    start = end - dt.timedelta(days=lookback_days)
    df = yf.Ticker(ticker).history(start=start, end=end, interval="1d", auto_adjust=False)
    if df.empty:
        raise ValueError(f"Keine Daily-Daten für {ticker} erhalten")
    return df.dropna(subset=["Open", "High", "Low", "Close", "Volume"])


def fetch_index_ratio(proxy_symbol: str, index_symbol: str) -> float:
    """Ratio index close / proxy close on the latest common trading day.

    Volume profiles are computed on a liquid proxy (ETF); knock-out certificates
    reference the index, so levels are multiplied by this ratio to get index levels.
    """
    proxy = fetch_daily(proxy_symbol, 14)["Close"]
    index = fetch_daily(index_symbol, 14)["Close"]
    # Compare by calendar date: the two series can carry different timezones.
    proxy.index = pd.to_datetime(proxy.index.date)
    index.index = pd.to_datetime(index.index.date)
    joined = pd.concat([proxy.rename("proxy"), index.rename("index")], axis=1, join="inner").dropna()
    if joined.empty:
        raise ValueError(f"Keine gemeinsamen Handelstage für {proxy_symbol} und {index_symbol}")
    last = joined.iloc[-1]
    return float(last["index"] / last["proxy"])


def fetch_intraday(ticker: str, interval: str, lookback_days: int) -> pd.DataFrame:
    end = dt.datetime.now(dt.timezone.utc)
    start = end - dt.timedelta(days=lookback_days)
    df = yf.Ticker(ticker).history(start=start, end=end, interval=interval, auto_adjust=False)
    if df.empty:
        logger.warning("Keine Intraday-Daten (%s) für %s erhalten", interval, ticker)
        return df
    return df.dropna(subset=["Open", "High", "Low", "Close", "Volume"])


def resample_to_4h(df_1h: pd.DataFrame) -> pd.DataFrame:
    if df_1h.empty:
        return df_1h
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    return df_1h.resample("4h").agg(agg).dropna(subset=["Open", "High", "Low", "Close"])


def fetch_fx_rate_usd_to_eur() -> float:
    """Näherungswert für 1 USD in EUR, mit Fallback falls der Abruf fehlschlägt."""
    try:
        fx = yf.Ticker("EURUSD=X").history(period="5d", interval="1d")
        eur_per_usd = 1 / float(fx["Close"].dropna().iloc[-1])
        return eur_per_usd
    except Exception:
        logger.warning("EURUSD-Kurs konnte nicht geladen werden, nutze Näherungswert 0.92")
        return 0.92


def get_currency(ticker: str) -> str:
    try:
        info = yf.Ticker(ticker).fast_info
        currency = info.get("currency")
        return (currency or "USD").upper()
    except Exception:
        return "USD"
