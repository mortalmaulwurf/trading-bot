"""Position sizing for the Strict Coach Mode rule set (knock-out certificates).

Information only - no order is ever placed automatically.

Rules implemented here:
- max risk per trade (optionally including fees and spread),
- variable leverage: the highest leverage whose knock-out barrier stays at least
  (1 + ko_buffer) * stop distance away from the entry, capped at max_leverage,
- capital per position capped at max_position_eur,
- net risk/reward after fees (flat fee below the free-volume threshold) and spread.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from .config import RiskSettings


@dataclass(frozen=True)
class PositionSuggestion:
    entry_price: float
    stop_price: float
    target_price: Optional[float]
    stop_distance_pct: float
    leverage: int
    max_leverage_by_buffer: int
    min_ko_distance_pct: float
    ko_level: float
    capital_eur: float
    exposure_eur: float
    costs_eur: float
    total_loss_eur: float
    capped: bool
    gross_crv: Optional[float]
    net_crv: Optional[float]
    required_target_price: float
    required_target_pct: float
    currency: str


def _fee_for(capital: float, settings: RiskSettings) -> float:
    return settings.fee_per_order_eur if capital < settings.min_free_order_volume_eur else 0.0


def _size(leverage: int, stop_fraction: float, settings: RiskSettings) -> tuple[float, float, float, float, bool]:
    """Returns (capital, exposure, costs, total_loss_at_stop, capped)."""
    spread = settings.spread_pct / 100
    risk = settings.max_risk_per_trade_eur
    if settings.risk_includes_costs:
        capital = risk / (leverage * stop_fraction + spread)
        for _ in range(6):  # the flat fee depends on the capital, so iterate to a fixed point
            fee = _fee_for(min(capital, settings.max_position_eur), settings)
            capital = max(0.0, risk - 2 * fee) / (leverage * stop_fraction + spread)
    else:
        capital = risk / (leverage * stop_fraction)

    capped = capital > settings.max_position_eur
    capital = min(capital, settings.max_position_eur)
    costs = 2 * _fee_for(capital, settings) + capital * spread
    exposure = capital * leverage
    total_loss = exposure * stop_fraction + costs
    return capital, exposure, costs, total_loss, capped


def suggest_position(
    entry_price: float,
    stop_price: float,
    target_price: Optional[float],
    currency: str,
    settings: RiskSettings,
) -> Optional[PositionSuggestion]:
    """Long-only suggestion. Returns None if the stop is not below the entry or sizing is impossible."""
    if stop_price >= entry_price or entry_price <= 0:
        return None

    stop_fraction = (entry_price - stop_price) / entry_price
    min_ko_fraction = stop_fraction * (1 + settings.ko_buffer)
    max_by_buffer = max(1, math.floor(1 / min_ko_fraction))
    leverage = min(max_by_buffer, int(settings.max_leverage))

    capital, exposure, costs, total_loss, capped = _size(leverage, stop_fraction, settings)
    if capital <= 0:
        return None

    gross_crv = net_crv = None
    if target_price is not None and target_price > entry_price:
        target_fraction = (target_price - entry_price) / entry_price
        gross_crv = target_fraction / stop_fraction
        net_crv = (exposure * target_fraction - costs) / total_loss

    # Smallest target move for which the net CRV reaches min_net_crv:
    # exposure * t - costs = m * (exposure * d + costs)  =>  t = m * d + (m + 1) * costs / exposure
    m = settings.min_net_crv
    required_fraction = m * stop_fraction + (m + 1) * costs / exposure

    return PositionSuggestion(
        entry_price=entry_price,
        stop_price=stop_price,
        target_price=target_price,
        stop_distance_pct=stop_fraction * 100,
        leverage=leverage,
        max_leverage_by_buffer=max_by_buffer,
        min_ko_distance_pct=min_ko_fraction * 100,
        ko_level=entry_price * (1 - 1 / leverage),
        capital_eur=capital,
        exposure_eur=exposure,
        costs_eur=costs,
        total_loss_eur=total_loss,
        capped=capped,
        gross_crv=gross_crv,
        net_crv=net_crv,
        required_target_price=entry_price * (1 + required_fraction),
        required_target_pct=required_fraction * 100,
        currency=currency,
    )
