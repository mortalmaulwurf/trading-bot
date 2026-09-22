"""Volumenprofil-Berechnung (POC / VAL / VAH) aus OHLCV-Daten.

yfinance liefert kein echtes Volumen-pro-Preis (kein Orderbuch/Tick-Feed).
Als Näherung wird das Tagesvolumen jeder Kerze proportional über ihre
Handelsspanne (Low-High) auf Preis-Bins verteilt – ein gängiger Ansatz,
wenn nur OHLCV-Daten verfügbar sind.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class VolumeProfile:
    poc: float
    val: float
    vah: float
    price_bin_edges: np.ndarray
    volume_by_bin: np.ndarray


def compute_volume_profile(df: pd.DataFrame, bins: int = 30, value_area_pct: float = 70.0) -> VolumeProfile:
    if df.empty:
        raise ValueError("Leerer DataFrame für Volumenprofil")

    price_low = float(df["Low"].min())
    price_high = float(df["High"].max())
    if price_high <= price_low:
        raise ValueError("Ungültige Preisspanne für Volumenprofil")

    edges = np.linspace(price_low, price_high, bins + 1)
    bin_volume = np.zeros(bins)

    for _, row in df.iterrows():
        low, high, vol = float(row["Low"]), float(row["High"]), float(row["Volume"])
        if vol <= 0:
            continue
        day_range = max(high - low, 1e-9)
        overlap_low = np.maximum(edges[:-1], low)
        overlap_high = np.minimum(edges[1:], high)
        overlap = np.clip(overlap_high - overlap_low, 0, None)
        bin_volume += (overlap / day_range) * vol

    total_volume = bin_volume.sum()
    if total_volume <= 0:
        raise ValueError("Kein Volumen für Volumenprofil vorhanden")

    poc_idx = int(np.argmax(bin_volume))
    poc_price = (edges[poc_idx] + edges[poc_idx + 1]) / 2

    # Value Area: von POC ausgehend jeweils die volumenstärkere Nachbar-Bin
    # dazunehmen, bis value_area_pct % des Gesamtvolumens erreicht sind.
    cum_volume = bin_volume[poc_idx]
    low_idx, high_idx = poc_idx, poc_idx
    target = total_volume * (value_area_pct / 100.0)

    while cum_volume < target and (low_idx > 0 or high_idx < bins - 1):
        vol_below = bin_volume[low_idx - 1] if low_idx > 0 else -1
        vol_above = bin_volume[high_idx + 1] if high_idx < bins - 1 else -1

        if vol_above >= vol_below:
            high_idx += 1
            cum_volume += bin_volume[high_idx]
        else:
            low_idx -= 1
            cum_volume += bin_volume[low_idx]

    val_price = edges[low_idx]
    vah_price = edges[high_idx + 1]

    return VolumeProfile(
        poc=poc_price, val=float(val_price), vah=float(vah_price),
        price_bin_edges=edges, volume_by_bin=bin_volume,
    )
