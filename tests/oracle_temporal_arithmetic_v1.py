"""Independent arithmetic oracle. Does not import the temporal implementation."""

from __future__ import annotations


def price_return(start: float, end: float) -> float:
    return end / start - 1.0


def grid_drawdown(prices: list[float], at: float) -> float:
    return at / max(prices) - 1.0


def retention(numerator: float, denominator: float) -> float:
    return numerator / denominator


def estimated_net_proxy(r_mark: float, h: float, q: float, r_fail: float, f: float) -> tuple[float, float]:
    success = (1.0 + r_mark) * (1.0 - h) - 1.0
    proxy = (1.0 - q) * success + q * r_fail - f
    return success, proxy


def break_even_haircut(r_mark: float, q: float, f: float) -> float:
    return 1.0 - (1.0 + f) / ((1.0 - q) * (1.0 + r_mark))


def missing_break_even_mean(observed: list[float], n_missing: int) -> float:
    return -sum(observed) / n_missing


def missing_stress_mean(observed: list[float], n_missing: int, stress: float = -1.0) -> float:
    return (sum(observed) + n_missing * stress) / (len(observed) + n_missing)
