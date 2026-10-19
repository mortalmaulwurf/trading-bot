"""Kernlogik: Level-Nähe erkennen und mit Reversal-/Timing-Signalen kombinieren."""
from __future__ import annotations

import logging
import datetime as dt
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from . import indicators
from .config import AnalysisSettings, RiskSettings
from .data_fetcher import fetch_daily, fetch_index_ratio, fetch_intraday, get_currency, resample_to_4h
from .events import get_upcoming_events
from .risk import PositionSuggestion, suggest_position
from .volume_profile import VolumeProfile, compute_volume_profile

logger = logging.getLogger(__name__)


@dataclass
class TickerAnalysis:
    ticker: str
    display_name: str
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
    upcoming_events: list[str]
    atr_value: Optional[float] = None
    target_name: Optional[str] = None
    is_actionable: bool = False
    is_a_setup: bool = False
    index_ratio: Optional[float] = None
    profile_basis: str = ""
    candles: list[dict[str, float | str]] = field(default_factory=list)
    daily_close_reversal: bool = False
    rule_checks: dict[str, Optional[bool | float]] = field(default_factory=dict)


CHART_CANDLES = 90


def _chart_candles(daily: pd.DataFrame, bars: int = CHART_CANDLES) -> list[dict[str, float | str]]:
    """Last ``bars`` daily candles as plain rows for the chart file."""
    tail = daily.tail(bars)
    return [
        {
            "t": ts.date().isoformat(),
            "o": round(float(row["Open"]), 4),
            "h": round(float(row["High"]), 4),
            "l": round(float(row["Low"]), 4),
            "c": round(float(row["Close"]), 4),
        }
        for ts, row in tail.iterrows()
    ]


def _confidence_label(confirmations: int) -> str:
    if confirmations >= 2:
        return "stark"
    if confirmations == 1:
        return "moderat"
    return "schwach (nur Level-Nähe)"


def _next_level_above(price: float, levels: dict[str, float]) -> tuple[Optional[str], Optional[float]]:
    """Nearest structural level above the price (used as the target), or (None, None)."""
    above = {name: lvl for name, lvl in levels.items() if lvl > price * 1.003}
    if not above:
        return None, None
    name = min(above, key=above.get)
    return name, above[name]


def _select_profile_frame(
    daily: pd.DataFrame, anchor_date: Optional[str], default_basis: str, min_bars: int = 10
) -> tuple[pd.DataFrame, str]:
    """Candles used for the profile: from the anchor date if set and long enough, else all."""
    if not anchor_date:
        return daily, default_basis
    anchor = pd.Timestamp(str(anchor_date))
    tz = getattr(daily.index, "tz", None)
    if tz is not None:
        anchor = anchor.tz_localize(tz)
    anchored = daily[daily.index >= anchor]
    if len(anchored) < min_bars:
        logger.warning(
            "Profil-Startdatum %s liefert nur %d Kerzen (< %d), nutze %s",
            anchor_date, len(anchored), min_bars, default_basis,
        )
        return daily, default_basis
    return anchored, f"ab {anchor.date().isoformat()}"


def analyze_ticker(
    ticker: str,
    analysis_settings: AnalysisSettings,
    risk_settings: RiskSettings,
    display_name: Optional[str] = None,
    index_symbol: Optional[str] = None,
    min_confirmations: int = 2,
) -> TickerAnalysis:
    anchor_date = analysis_settings.profile_anchor_date
    lookback_days = analysis_settings.lookback_days_daily
    if anchor_date:
        days_since_anchor = (dt.date.today() - dt.date.fromisoformat(str(anchor_date))).days
        lookback_days = max(lookback_days, days_since_anchor + 7)
    daily = fetch_daily(ticker, lookback_days)
    profile_frame, profile_basis = _select_profile_frame(
        daily, anchor_date, f"{analysis_settings.lookback_days_daily} Tage"
    )
    profile = compute_volume_profile(
        profile_frame, bins=analysis_settings.volume_profile_bins, value_area_pct=analysis_settings.value_area_pct
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

    upcoming_events: list[str] = []
    try:
        upcoming_events = get_upcoming_events(ticker, currency, analysis_settings.upcoming_events_days_ahead)
    except Exception as exc:
        logger.warning("Bevorstehende Termine für %s nicht abrufbar: %s", ticker, exc)

    # Plan (long only): stop = hit level minus ATR, target = nearest structural level above the price.
    # Informational only; sizing and net CRV follow the risk settings.
    atr_value = indicators.atr(daily, period=risk_settings.atr_period)
    if atr_value is not None:
        stop_price = nearest_price - atr_value * risk_settings.stop_atr_multiple
    else:
        stop_price = nearest_price * 0.99  # fallback without ATR: 1% below the level
    target_levels = {"POC": profile.poc, "VAH": profile.vah}
    if long_profile is not None:
        target_levels.update(
            {"langfristiges POC": long_profile.poc, "langfristiges VAH": long_profile.vah}
        )
    target_name, target_price = _next_level_above(current_price, target_levels)

    position_suggestion = None
    if is_hit:
        position_suggestion = suggest_position(current_price, stop_price, target_price, currency, risk_settings)

    daily_reversal = indicators.daily_close_reversal(
        daily,
        nearest_price,
        tolerance_pct=analysis_settings.reversal_test_tolerance_pct,
        lookback_bars=analysis_settings.reversal_lookback_bars,
    )
    reversal_ok = daily_reversal or not analysis_settings.require_daily_close_reversal
    confirmations_ok = confirmations >= min_confirmations
    net_crv = position_suggestion.net_crv if position_suggestion is not None else None
    net_crv_ok = net_crv is not None and net_crv >= risk_settings.min_net_crv

    # Rule checks are stored as-is so the report and dashboard can show why a hit did not alert.
    rule_checks: dict[str, Optional[bool | float]] = {
        "level_hit": is_hit,
        "daily_close_reversal": daily_reversal,
        "reversal_required": analysis_settings.require_daily_close_reversal,
        "confirmations_ok": confirmations_ok,
        "net_crv": net_crv,
        "net_crv_ok": net_crv_ok,
    }

    is_actionable = bool(is_hit and reversal_ok and confirmations_ok and net_crv_ok)
    is_a_setup = bool(
        is_actionable and position_suggestion.net_crv >= risk_settings.a_setup_net_crv
    )

    index_ratio = None
    if index_symbol and is_hit:
        try:
            index_ratio = fetch_index_ratio(ticker, index_symbol)
        except Exception as exc:
            logger.warning("Index-Umrechnung für %s (%s) nicht verfügbar: %s", ticker, index_symbol, exc)

    return TickerAnalysis(
        ticker=ticker,
        display_name=display_name or ticker,
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
        upcoming_events=upcoming_events,
        atr_value=atr_value,
        target_name=target_name,
        is_actionable=is_actionable,
        is_a_setup=is_a_setup,
        index_ratio=index_ratio,
        profile_basis=profile_basis,
        candles=_chart_candles(daily),
        daily_close_reversal=daily_reversal,
        rule_checks=rule_checks,
    )
