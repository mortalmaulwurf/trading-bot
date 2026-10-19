"""German number formatting shared by the HTML report modules."""
from __future__ import annotations


def de(value: float, digits: int = 2) -> str:
    return f"{value:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def price(value: float) -> str:
    """Two to four decimals, like the dashboard."""
    whole, decimals = f"{value:,.4f}".split(".")
    return f"{whole.replace(',', '.')},{decimals.rstrip('0').ljust(2, '0')}"
