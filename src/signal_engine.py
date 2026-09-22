"""Kernlogik: Level-Nähe erkennen und mit Reversal-/Timing-Signalen kombinieren."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from . import indicators
from .config import AnalysisSettings, RiskSettings
from .data_fetcher import fetch_daily, fetch_intraday, get_currency, resample_to_4h
from .risk import PositionSuggestion, suggest_position
from .volume_profile import VolumeProfile, compute_volume_profile

logger = logging.getLogger(__name__)


@dataclass
class TickerAnalysis:
    ticker: str
    current_price: float
    currency: str
    profile: VolumeProfile
    nearest_level_name: str
    nearest_level_price: float
    distance_pct: float
    is_hit: bool
    rsi_value: Optional[float]
    rsi_oversold: bool
    volume_spike: bool
    intraday_momentum_up: bool
    confirmations: int
    confidence: str
    position_suggestion: Optional[PositionSuggestion]
    long_profile: Optional[VolumeProfile]
    confluence: bool
    confluence_level_name: Optional[str]
    weekly_trend: Optional[str]
    weekly_sma: Optional[float]


def _confidence_label(confirmations: int) -> str:
    if confirmations >= 2:
        return "stark"
    if confirmations == 1:
        return "moderat"
    return "schwach (nur Level-Nähe)"


def analyze_ticker(
    ticker: str,
    analysis_settings: AnalysisSettings,
    risk_settings: RiskSettings,
    fx_rate_usd_eur: float,
) -> TickerAnalysis:
    daily = fetch_daily(ticker, analysis_settings.lookback_days_daily)
    profile = compute_volume_profile(
        daily, bins=analysis_settings.volume_profile_bins, value_area_pct=analysis_settings.value_area_pct
    )
    current_price = float(daily["Close"].iloc[-1])
    currency = get_currency(ticker)

    # Nur POC und VAL gelten hier als strukturelle Unterstützungen (VAH ist
    # eher Widerstand); die Nähe-Prüfung bezieht sich bewusst nur auf diese beiden.
    levels = {"POC": profile.poc, "VAL": profile.val}
    nearest_name, nearest_price = min(
        levels.items(), key=lambda item: abs(current_price - item[1]) / current_price
    )
    distance_pct = (current_price - nearest_price) / nearest_price * 100
    is_hit = abs(distance_pct) <= analysis_settings.proximity_threshold_pct

    rsi_series = indicators.rsi(daily["Close"], period=analysis_settings.rsi_period)
    last_rsi = rsi_series.iloc[-1] if not rsi_series.empty else None
    rsi_value = float(last_rsi) if last_rsi is not None and not pd.isna(last_rsi) else None
    rsi_oversold = bool(rsi_value is not None and rsi_value <= analysis_settings.rsi_oversold)

    volume_spike = indicators.is_volume_spike(
        daily, lookback=analysis_settings.volume_spike_lookback, multiplier=analysis_settings.volume_spike_multiplier
    )

    intraday_momentum_up = False
    try:
        intraday_1h = fetch_intraday(
            ticker, analysis_settings.intraday_interval, analysis_settings.intraday_lookback_days
        )
        intraday_4h = resample_to_4h(intraday_1h)
        intraday_momentum_up = indicators.intraday_momentum_turning_up(
            intraday_4h
        ) or indicators.intraday_momentum_turning_up(intraday_1h)
    except Exception as exc:
        logger.warning("Intraday-Daten für %s nicht verfügbar: %s", ticker, exc)

    confirmations = sum([rsi_oversold, volume_spike, intraday_momentum_up])

    position_suggestion = None
    if is_hit:
        fx_rate = 1.0 if currency == "EUR" else fx_rate_usd_eur
        # Stop-Referenz nur zur Größenberechnung: 1% Puffer unter VAL, keine Handelsempfehlung.
        stop_price = profile.val * 0.99
        position_suggestion = suggest_position(current_price, stop_price, currency, fx_rate, risk_settings)

    # Langfristiges Volumenprofil (Konfluenz) und Wochentrend – beides nur
    # Zusatzkontext, kein Ausschlusskriterium; scheitert der Abruf, läuft die
    # Kernanalyse trotzdem weiter (analog zur Intraday-Komponente oben).
    long_profile = None
    confluence = False
    confluence_level_name = None
    weekly_trend_value = None
    weekly_sma = None
    try:
        long_daily = fetch_daily(ticker, analysis_settings.lookback_days_long)
        long_profile = compute_volume_profile(
            long_daily, bins=analysis_settings.volume_profile_bins, value_area_pct=analysis_settings.value_area_pct
        )
        weekly_trend_value, weekly_sma = indicators.weekly_trend(
            long_daily, sma_periods=analysis_settings.weekly_trend_sma_periods
        )

        if is_hit:
            long_levels = {"langfristiges POC": long_profile.poc, "langfristiges VAL": long_profile.val}
            closest_long_name, closest_long_price = min(
                long_levels.items(), key=lambda item: abs(nearest_price - item[1]) / nearest_price
            )
            confluence_distance_pct = abs(nearest_price - closest_long_price) / nearest_price * 100
            if confluence_distance_pct <= analysis_settings.confluence_threshold_pct:
                confluence = True
                confluence_level_name = closest_long_name
    except Exception as exc:
        logger.warning("Langfristiges Volumenprofil für %s nicht verfügbar: %s", ticker, exc)

    return TickerAnalysis(
        ticker=ticker,
        current_price=current_price,
        currency=currency,
        profile=profile,
        nearest_level_name=nearest_name,
        nearest_level_price=nearest_price,
        distance_pct=distance_pct,
        is_hit=is_hit,
        rsi_value=rsi_value,
        rsi_oversold=rsi_oversold,
        volume_spike=volume_spike,
        intraday_momentum_up=intraday_momentum_up,
        confirmations=confirmations,
        confidence=_confidence_label(confirmations),
        position_suggestion=position_suggestion,
        long_profile=long_profile,
        confluence=confluence,
        confluence_level_name=confluence_level_name,
        weekly_trend=weekly_trend_value,
        weekly_sma=weekly_sma,
    )
