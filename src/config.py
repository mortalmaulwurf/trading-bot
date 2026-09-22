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
    shot_size_eur: float
    max_risk_per_trade_eur: float
    leverage: float


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


@dataclass(frozen=True)
class Settings:
    risk: RiskSettings
    analysis: AnalysisSettings


def load_settings(path: Optional[Path] = None) -> Settings:
    path = path or CONFIG_DIR / "settings.yaml"
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    return Settings(
        risk=RiskSettings(**raw["risk"]),
        analysis=AnalysisSettings(**raw["analysis"]),
    )


def load_watchlist(path: Optional[Path] = None) -> list[str]:
    path = path or CONFIG_DIR / "watchlist.yaml"
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return list(raw["tickers"])


def get_telegram_credentials() -> tuple[Optional[str], Optional[str]]:
    return os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
