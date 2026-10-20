"""Rule traffic lights per instrument, derived from latest.json (same semantics as the dashboard)."""
from __future__ import annotations

from dataclasses import dataclass

from .formatting import de as _de


@dataclass(frozen=True)
class Light:
    id: str
    label: str
    state: str  # pass | fail | neutral | unknown
    detail: str


def rule_lights(result: dict, rule_set: dict) -> list[Light]:
    checks = result.get("rule_checks") or {}
    reversal_ok = bool(checks.get("daily_close_reversal"))
    reversal_required = bool(checks.get("reversal_required", True))
    candle = checks.get("daily_candle_bullish")
    net_crv = checks.get("net_crv")
    level_hit = bool(checks.get("level_hit"))
    min_crv = rule_set["min_net_crv"]

    if reversal_ok:
        reversal = Light("reversal", "Tagesschluss-Umkehr", "pass", "bestätigt")
    elif not reversal_required:
        reversal = Light("reversal", "Tagesschluss-Umkehr", "neutral", "nicht erforderlich")
    else:
        reversal = Light("reversal", "Tagesschluss-Umkehr", "fail", "nicht bestätigt")

    # The reversal check already contains the candle when the bot requires it, so a red candle only counts
    # as failed while the reversal itself fails.
    if candle is None:
        bullish = Light("bullish_candle", "Grüne Tageskerze", "unknown", "keine Info")
    elif candle:
        bullish = Light("bullish_candle", "Grüne Tageskerze", "pass", "Schluss über Eröffnung")
    elif reversal_required and not reversal_ok:
        bullish = Light("bullish_candle", "Grüne Tageskerze", "fail", "Schluss unter Eröffnung")
    else:
        bullish = Light("bullish_candle", "Grüne Tageskerze", "neutral", "rot, nicht relevant")

    crv_label = f"Netto-CRV ≥ {_de(min_crv)}:1"
    if net_crv is None:
        crv = (
            Light("net_crv", crv_label, "fail", "kein berechenbarer Plan")
            if level_hit
            else Light("net_crv", crv_label, "unknown", "kein Plan ohne Level-Treffer")
        )
    else:
        crv = Light("net_crv", crv_label, "pass" if net_crv >= min_crv else "fail", f"{_de(net_crv)}:1")

    distance = result["distance_pct"]
    level = Light(
        "level_hit",
        "Level-Treffer",
        "pass" if level_hit else "fail",
        f"{result['nearest_level_name']} {'+' if distance >= 0 else '−'}{_de(abs(distance))}\u00a0%",
    )
    return [level, reversal, bullish, crv]


def is_paper_candidate(result: dict, rule_set: dict) -> bool:
    """Paper trade for the journal: all rules pass except a net CRV between the paper and the real minimum.

    Display hint only (no push). Reports without ``paper_net_crv`` have no paper tier.
    """
    checks = result.get("rule_checks") or {}
    if result.get("is_actionable") or not checks.get("level_hit") or not checks.get("confirmations_ok"):
        return False
    reversal_ok = bool(checks.get("daily_close_reversal")) or not checks.get("reversal_required", True)
    net_crv = checks.get("net_crv")
    min_crv = rule_set["min_net_crv"]
    paper_min = rule_set.get("paper_net_crv", min_crv)
    return bool(reversal_ok and net_crv is not None and paper_min <= net_crv < min_crv)
