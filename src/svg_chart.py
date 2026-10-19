"""Inline SVG candlestick chart with level lines. No external scripts or fonts."""
from __future__ import annotations

import html as html_lib
from typing import Optional

from .formatting import price as _price

WIDTH, HEIGHT, LABEL_WIDTH, PAD_Y = 380, 190, 100, 10
MIN_LABEL_GAP = 12


def spread_labels(ys: list[float], gap: float, top: float, bottom: float) -> list[float]:
    """Pushes labels apart top to bottom so they stay readable, and keeps the stack inside the bottom edge."""
    order = sorted(range(len(ys)), key=lambda i: ys[i])
    placed: list[float] = []
    previous = top - gap
    for i in order:
        y = max(ys[i], previous + gap)
        placed.append(y)
        previous = y
    limit = bottom
    for k in range(len(placed) - 1, -1, -1):
        placed[k] = min(placed[k], limit)
        limit = placed[k] - gap
    result = [0.0] * len(ys)
    for k, i in enumerate(order):
        result[i] = placed[k]
    return result


def _num(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def render_chart(name: str, candles: list[dict], levels: list[dict]) -> str:
    """``levels``: dicts with id, label, price, tone (level | entry | stop | target)."""
    if not candles:
        return ""
    levels = [lv for lv in levels if lv.get("price") is not None]
    prices = [c["h"] for c in candles] + [c["l"] for c in candles] + [lv["price"] for lv in levels]
    raw_min, raw_max = min(prices), max(prices)
    pad = ((raw_max - raw_min) or abs(raw_max) * 0.01 or 1) * 0.04
    low, high = raw_min - pad, raw_max + pad
    top, bottom = PAD_Y, HEIGHT - PAD_Y
    plot_right = WIDTH - LABEL_WIDTH

    def y_of(price: float) -> float:
        return top + (high - price) / (high - low) * (bottom - top)

    slot = plot_right / len(candles)
    body_w = max(1.0, slot * 0.62)
    level_ys = [y_of(lv["price"]) for lv in levels]
    label_ys = spread_labels(level_ys, MIN_LABEL_GAP, top, bottom)

    parts = [
        f'<svg class="chart" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" '
        f'aria-label="{html_lib.escape(_summary(name, candles, levels), quote=True)}" preserveAspectRatio="xMidYMid meet">'
    ]
    for lv, y in zip(levels, level_ys):
        parts.append(f'<line class="chart-line chart-line--{lv["tone"]}" x1="0" x2="{_num(plot_right)}" y1="{_num(y)}" y2="{_num(y)}"/>')
    for i, c in enumerate(candles):
        x = slot * i + slot / 2
        body_top, body_bottom = y_of(max(c["o"], c["c"])), y_of(min(c["o"], c["c"]))
        cls = "up" if c["c"] >= c["o"] else "down"
        parts.append(
            f'<g class="chart-candle chart-candle--{cls}"><line x1="{_num(x)}" x2="{_num(x)}" y1="{_num(y_of(c["h"]))}" y2="{_num(y_of(c["l"]))}"/>'
            f'<rect x="{_num(x - body_w / 2)}" y="{_num(body_top)}" width="{_num(body_w)}" height="{_num(max(1.0, body_bottom - body_top))}"/></g>'
        )
    for lv, ly in zip(levels, label_ys):
        parts.append(
            f'<text class="chart-label chart-label--{lv["tone"]}" x="{_num(plot_right + 6)}" y="{_num(ly)}" '
            f'dominant-baseline="middle">{html_lib.escape(lv["label"])} {_price(lv["price"])}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _summary(name: str, candles: list[dict], levels: list[dict]) -> str:
    last: Optional[dict] = candles[-1] if candles else None
    close = f", letzter Schluss {_price(last['c'])}" if last else ""
    return f"Kerzenchart {name}, {len(candles)} Tage{close}. " + ", ".join(f"{lv['label']} {_price(lv['price'])}" for lv in levels)
