from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

MILLIUNIT = Decimal("0.001")


def to_milliunits(value: float | int | Decimal | None) -> int:
    if value is None:
        return 0
    quantized = Decimal(str(value)).quantize(MILLIUNIT, rounding=ROUND_HALF_UP)
    return int(quantized * 1000)


def from_milliunits(value: int) -> float:
    return float(Decimal(value) / Decimal(1000))
