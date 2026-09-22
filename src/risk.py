"""Positionsgrößen-Vorschlag nach dem Strict-Coach-Mode-Risikorahmen.

Reine Informationsausgabe zur gemeinsamen Diskussion des Einstiegs –
es wird an keiner Stelle automatisch eine Order platziert.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .config import RiskSettings


@dataclass(frozen=True)
class PositionSuggestion:
    entry_price: float
    stop_price: float
    stop_distance_pct: float
    shares: float
    position_value_eur: float
    margin_required_eur: float
    currency: str
    fx_rate_to_eur: float


def suggest_position(
    entry_price: float,
    stop_price: float,
    currency: str,
    fx_rate_to_eur: float,
    risk_settings: RiskSettings,
) -> Optional[PositionSuggestion]:
    stop_distance = entry_price - stop_price
    if stop_distance <= 0:
        return None

    stop_distance_eur = stop_distance * fx_rate_to_eur
    shares = risk_settings.max_risk_per_trade_eur / stop_distance_eur
    position_value_eur = shares * entry_price * fx_rate_to_eur
    margin_required_eur = position_value_eur / risk_settings.leverage

    return PositionSuggestion(
        entry_price=entry_price,
        stop_price=stop_price,
        stop_distance_pct=(stop_distance / entry_price) * 100,
        shares=shares,
        position_value_eur=position_value_eur,
        margin_required_eur=margin_required_eur,
        currency=currency,
        fx_rate_to_eur=fx_rate_to_eur,
    )
