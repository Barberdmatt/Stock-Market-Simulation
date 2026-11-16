"""Stylized-fact diagnostics. Work on any (event_time, bid, ask) + market-order record,
so the same code scores simulated and real data."""
import numpy as np


def mid_series(t, bid, ask):
    mid = (np.asarray(bid, float) + np.asarray(ask, float)) / 2
    ok = np.isfinite(mid)
    return np.asarray(t)[ok], mid[ok]


def grid_mid(t, mid, dt):
    """Mid-price sampled on a regular time grid (last observation carried forward)."""
    g = np.arange(t[0] + dt, t[-1], dt)
    return mid[np.searchsorted(t, g, side="right") - 1]


def acf(x, lags):
    x = np.asarray(x, float) - np.mean(x)
    v = np.dot(x, x)
    return np.array([np.dot(x[:-l], x[l:]) / v if l < len(x) else np.nan for l in lags])


def kurtosis(x):
    x = np.asarray(x, float)
    s = x.std()
    return np.mean(((x - x.mean()) / s) ** 4) - 3 if s > 0 else np.nan


def hill_tail(x, frac=0.02):
    """Hill estimator of the tail exponent of |x| (largest `frac` of non-zero obs)."""
    a = np.sort(np.abs(x[x != 0]))[::-1]
    k = max(10, int(frac * len(a)))
    return 1.0 / np.mean(np.log(a[:k] / a[k])) if len(a) > k else np.nan


def variance_ratio(mid, q):
    d1 = np.diff(mid)
    dq = mid[q:] - mid[:-q]
    return dq.var() / (q * d1.var())


def sign_acf_exponent(signs, max_lag=300):
    """Slope gamma of ACF(l) ~ l^-gamma for the order-sign series (positive-ACF lags only)."""
    lags = np.unique(np.logspace(0, np.log10(max_lag), 25).astype(int))
    a = acf(signs, lags)
    ok = a > 0
    if ok.sum() < 4:
        return np.nan, a[:1][0] if len(a) else np.nan
    return -np.polyfit(np.log(lags[ok]), np.log(a[ok]), 1)[0], a[0]


def impact_curve(side, size, mid0, mid1, nbins=10):
    """Mean signed mid move (ticks) vs market-order size (log-spaced quantile bins)."""
    ok = np.isfinite(mid0) & np.isfinite(mid1)
    s, q, dm = side[ok], size[ok], (mid1[ok] - mid0[ok]) * side[ok]
    edges = np.unique(np.quantile(q, np.linspace(0, 1, nbins + 1)))
    idx = np.clip(np.searchsorted(edges, q, side="right") - 1, 0, len(edges) - 2)
    x = np.array([q[idx == i].mean() for i in range(len(edges) - 1) if (idx == i).any()])
    y = np.array([dm[idx == i].mean() for i in range(len(edges) - 1) if (idx == i).any()])
    ok = y > 0
    slope = np.polyfit(np.log(x[ok]), np.log(y[ok]), 1)[0] if ok.sum() >= 3 else np.nan
    return x, y, slope


def summary(t, bid, ask, mo_side, mo_size=None, mo_mid0=None, mo_mid1=None,
            dt=1.0, q=30):
    tm, mid = mid_series(t, bid, ask)
    g = grid_mid(tm, mid, dt)
    r = np.diff(np.log(g))
    out = {
        "return kurtosis (dt=%gs)" % dt: kurtosis(r),
        "Hill tail index of |r|": hill_tail(r),
        "ACF(1) of returns": acf(r, [1])[0],
        "ACF(1) of |returns|": acf(np.abs(r), [1])[0],
        "ACF(30) of |returns|": acf(np.abs(r), [30])[0],
        "ACF(300) of |returns|": acf(np.abs(r), [300])[0],
        "variance ratio VR(%d)" % q: variance_ratio(g, q),
    }
    sp = np.asarray(ask) - np.asarray(bid)
    sp = sp[np.isfinite(sp)]
    out["mean spread (ticks)"] = sp.mean()
    out["P(spread = 1 tick)"] = np.mean(sp == 1)
    gam, a1 = sign_acf_exponent(np.asarray(mo_side))
    out["order-sign ACF(1)"] = a1
    out["order-sign ACF decay exponent"] = gam
    if mo_size is not None:
        _, _, slope = impact_curve(np.asarray(mo_side), np.asarray(mo_size),
                                   np.asarray(mo_mid0), np.asarray(mo_mid1))
        out["impact exponent (dp ~ Q^x)"] = slope
    return out
