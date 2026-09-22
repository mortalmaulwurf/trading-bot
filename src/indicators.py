"""Einfache technische Indikatoren: RSI, Volumen-Spike, Intraday-Momentum."""
from __future__ import annotations

import pandas as pd


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))


def is_volume_spike(df: pd.DataFrame, lookback: int = 20, multiplier: float = 1.5) -> bool:
    if len(df) < lookback + 1:
        return False
    avg_volume = df["Volume"].iloc[-(lookback + 1):-1].mean()
    last_volume = df["Volume"].iloc[-1]
    return bool(avg_volume > 0 and last_volume >= avg_volume * multiplier)


def intraday_momentum_turning_up(df_intraday: pd.DataFrame, lookback_bars: int = 6) -> bool:
    """Grobe Timing-Heuristik: Lag das jüngste Tief nicht auf der letzten Kerze
    und notiert der aktuelle Kurs bereits wieder darüber? Deutet auf eine
    beginnende kurzfristige Erholung hin (kein vollständiges Candlestick-Pattern)."""
    if len(df_intraday) < lookback_bars + 1:
        return False
    recent = df_intraday["Close"].iloc[-(lookback_bars + 1):]
    lowest_pos = int(recent.values.argmin())
    return bool(lowest_pos < len(recent) - 1 and recent.iloc[-1] > recent.iloc[lowest_pos])
