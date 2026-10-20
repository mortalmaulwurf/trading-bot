"""Laden von Konfiguration (YAML) und Secrets (.env / Umgebungsvariablen)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"

# Lädt lokale .env-Datei, falls vorhanden. In GitHub Actions kommen die Werte
# stattdessen direkt als echte Umgebungsvariablen aus den Repository-Secrets.
load_dotenv(REPO_ROOT / ".env")


@dataclass(frozen=True)
class RiskSettings:
    total_capital_eur: float
    max_position_eur: float
    max_risk_per_trade_eur: float
    ko_buffer: float
    max_leverage: int
    fee_per_order_eur: float
    min_free_order_volume_eur: float
    spread_pct: float
    risk_includes_costs: bool
    min_net_crv: float
    a_setup_net_crv: float
    atr_period: int
    stop_atr_multiple: float
    # Display-only tier: setups between this and min_net_crv count as paper trades (no push).
    paper_net_crv: float = 2.0


@dataclass(frozen=True)
class AnalysisSettings:
    lookback_days_daily: int
    intraday_interval: str
    intraday_lookback_days: int
    proximity_threshold_pct: float
    value_area_pct: float
    volume_profile_bins: int
    rsi_period: int
    rsi_oversold: float
    rsi_overbought: float
    volume_spike_multiplier: float
    volume_spike_lookback: int
    lookback_days_long: int
    confluence_threshold_pct: float
    weekly_trend_sma_periods: int
    upcoming_events_days_ahead: int
    # Optional anchor date (YYYY-MM-DD) for a fixed-range volume profile.
    profile_anchor_date: Optional[str] = None
    # Rule set: confirmed reversal = zone tested within the last N daily bars and the
    # latest daily close is back above the level.
    require_daily_close_reversal: bool = True
    reversal_test_tolerance_pct: float = 0.5
    reversal_lookback_bars: int = 3
    reversal_require_bullish_candle: bool = True


@dataclass(frozen=True)
class NotificationSettings:
    site_url: str = ""
    min_confirmations: int = 2


@dataclass(frozen=True)
class Settings:
    risk: RiskSettings
    analysis: AnalysisSettings
    notifications: NotificationSettings


@dataclass(frozen=True)
class WatchlistEntry:
    symbol: str
    name: str
    # Optional: underlying index symbol (e.g. "^GDAXI") used to translate ETF
    # levels into index levels, because knock-out certificates reference the index.
    index_symbol: Optional[str] = None


def load_settings(path: Optional[Path] = None) -> Settings:
    path = path or CONFIG_DIR / "settings.yaml"
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    analysis_raw = dict(raw["analysis"])
    if analysis_raw.get("profile_anchor_date") is not None:
        analysis_raw["profile_anchor_date"] = str(analysis_raw["profile_anchor_date"])

    return Settings(
        risk=RiskSettings(**raw["risk"]),
        analysis=AnalysisSettings(**analysis_raw),
        notifications=NotificationSettings(**raw.get("notifications", {})),
    )


def load_watchlist(path: Optional[Path] = None) -> list[WatchlistEntry]:
    path = path or CONFIG_DIR / "watchlist.yaml"
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    entries = []
    for item in raw["tickers"]:
        if isinstance(item, str):
            entries.append(WatchlistEntry(symbol=item, name=item))
        else:
            entries.append(
                WatchlistEntry(
                    symbol=item["symbol"],
                    name=item.get("name", item["symbol"]),
                    index_symbol=item.get("index_symbol"),
                )
            )
    return entries


def get_telegram_credentials() -> tuple[Optional[str], Optional[str]]:
    return os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
