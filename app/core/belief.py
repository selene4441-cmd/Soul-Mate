from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class BetaPosterior:
    alpha: float
    beta: float

    def __post_init__(self) -> None:
        if not (self.alpha > 0.0 and self.beta > 0.0):
            raise ValueError("alpha and beta must be > 0")

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    @property
    def strength(self) -> float:
        return self.alpha + self.beta


@dataclass(frozen=True)
class Evidence:
    positive: float = 0.0
    negative: float = 0.0

    def __post_init__(self) -> None:
        if self.positive < 0 or self.negative < 0:
            raise ValueError("evidence counts must be >= 0")


def update(posterior: BetaPosterior, evidence: Evidence | tuple[float, float]) -> BetaPosterior:
    if isinstance(evidence, tuple):
        evidence = Evidence(positive=float(evidence[0]), negative=float(evidence[1]))
    return BetaPosterior(
        alpha=posterior.alpha + evidence.positive,
        beta=posterior.beta + evidence.negative,
    )


def entropy(p: float) -> float:
    """
    Bernoulli entropy: H(p) = -p ln p - (1-p) ln(1-p), with 0 ln 0 := 0.
    """
    if p < 0.0 or p > 1.0:
        raise ValueError("p must be in [0, 1]")
    if p == 0.0 or p == 1.0:
        return 0.0
    return -(p * math.log(p) + (1.0 - p) * math.log(1.0 - p))


def confidence_interval(
    posterior: BetaPosterior, *, level: float = 0.95, tol: float = 1e-10
) -> tuple[float, float]:
    if level <= 0.0 or level >= 1.0:
        raise ValueError("level must be in (0, 1)")
    lo_q = (1.0 - level) / 2.0
    hi_q = 1.0 - lo_q
    lo = _beta_ppf(lo_q, posterior.alpha, posterior.beta, tol=tol)
    hi = _beta_ppf(hi_q, posterior.alpha, posterior.beta, tol=tol)
    return (lo, hi)


def _log_beta(a: float, b: float) -> float:
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def _betacf(a: float, b: float, x: float) -> float:
    # Continued fraction for incomplete beta (Numerical Recipes).
    max_iter = 200
    eps = 3e-14
    fpmin = 1e-300

    qab = a + b
    qap = a + 1.0
    qam = a - 1.0

    c = 1.0
    d = 1.0 - (qab * x) / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d

    for m in range(1, max_iter + 1):
        m2 = 2 * m

        aa = (m * (b - m) * x) / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c

        aa = -((a + m) * (qab + m) * x) / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta

        if abs(delta - 1.0) < eps:
            break

    return h


def _beta_cdf(x: float, a: float, b: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0

    # Regularized incomplete beta I_x(a,b)
    ln_bt = (a * math.log(x) + b * math.log(1.0 - x)) - _log_beta(a, b)
    bt = math.exp(ln_bt)

    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def _beta_ppf(q: float, a: float, b: float, *, tol: float = 1e-10) -> float:
    if q < 0.0 or q > 1.0:
        raise ValueError("q must be in [0, 1]")
    if q == 0.0:
        return 0.0
    if q == 1.0:
        return 1.0

    lo = 0.0
    hi = 1.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        cdf = _beta_cdf(mid, a, b)
        if abs(cdf - q) <= tol:
            return mid
        if cdf < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def entropies(values: Iterable[float]) -> list[float]:
    return [entropy(v) for v in values]

