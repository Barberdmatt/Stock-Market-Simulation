"""Event-driven LOB simulator with a calibratable order-flow model.

Order flow (all times in seconds):
  * Market orders: 2-D (buy/sell) Hawkes process, kernel = sum of K exponentials
        phi_k(t) = n_k * beta_k * exp(-beta_k t)      (n_k = branching mass)
    same-side mass `n_same`, cross-side mass `n_cross`. A sum of exponentials
    over several decades of time scale mimics the power-law memory of order signs.
  * Limit orders: Poisson per side, rate lim_rate * (1 -/+ kappa*tanh(z/z_scale)),
    where z is an exponentially decaying signed market-order counter. kappa>0 makes
    liquidity refill on the side that was just consumed (the mechanism that keeps
    prices ~diffusive despite persistent order signs).
    Placement (same for both sides): if the spread is > 1 tick, with prob `p_imp` the order
    lands uniformly INSIDE the spread; otherwise it lands d ticks behind-or-at its own best
    quote (d=1 joins the touch), 1<=d<=dmax, with
        P(d) ~ d^g * (1 + d/d0)^-(g + 1 + alpha)
    (rises like d^g near the touch -> hump-shaped book -> concave impact; power-law tail alpha).
  * Cancellations: each resting order cancels at rate `cancel_rate`.
  * Sizes: discretised log-normal.
Event times are simulated exactly by Ogata thinning.
"""
import bisect
import math
import random
from array import array
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from .book import Book, BID, ASK

NAN = float("nan")


@dataclass
class Params:
    mu: float = 0.05                          # baseline MO intensity per side (1/s)
    betas: tuple = (5.0, 0.5, 0.02)           # kernel decay rates (1/s)
    n_same: tuple = (0.15, 0.25, 0.45)        # same-side branching mass per kernel
    n_cross: tuple = (0.02, 0.03, 0.05)       # cross-side branching mass per kernel
    lim_rate: float = 1.5                     # baseline limit-order rate per side (1/s)
    cancel_rate: float = 0.01                 # per-order cancel rate (1/s)
    place_alpha: float = 1.0                  # tail exponent of placement distance
    place_d0: float = 4.0                     # scale (ticks) where the tail starts
    place_g: float = 1.0                      # near-touch growth exponent (0 = monotone)
    place_dmax: int = 100
    p_imp: float = 0.3                        # prob. a new order improves the quote when spread > 1
    mo_mu: float = 1.0                        # log-normal params of market-order size
    mo_sigma: float = 1.0
    lo_mu: float = 1.5                        # log-normal params of limit-order size
    lo_sigma: float = 0.8
    kappa: float = 0.5                        # liquidity response strength in [0,1)
    z_beta: float = 0.2                       # decay rate of signed-flow memory z
    z_scale: float = 3.0
    p0: int = 10000                           # starting price (ticks)

    def branching_ratio(self):
        return sum(self.n_same) + sum(self.n_cross)

    def asdict(self):
        return asdict(self)


@dataclass
class Result:
    t: np.ndarray            # event times
    bid: np.ndarray          # best bid after each event (nan if empty)
    ask: np.ndarray
    mo_t: np.ndarray         # market orders: time, side (+1 buy), size, mid before/after
    mo_side: np.ndarray
    mo_size: np.ndarray
    mo_mid0: np.ndarray
    mo_mid1: np.ndarray
    depth: np.ndarray        # mean depth profile, shape (2, maxd): [bid, ask] at distance 0..maxd-1 from best
    messages: pd.DataFrame | None = None

    @property
    def mid(self):
        return (self.bid + self.ask) / 2


def place_pmf(alpha, d0, g, dmax):
    d = np.arange(1, dmax + 1, dtype=float)
    w = d ** g * (1.0 + d / d0) ** (-(g + 1.0 + alpha))
    return w / w.sum()


def _run(p: Params, n_events: int, seed: int = 0, record_messages: bool = False,
         snapshot_every: int = 200, depth_levels: int = 30,
         book: Book | None = None, on_fill=None):
    rng = random.Random(seed)
    K = len(p.betas)
    betas = p.betas
    a_same = [p.n_same[k] * betas[k] for k in range(K)]
    a_cross = [p.n_cross[k] * betas[k] for k in range(K)]
    R0 = [0.0] * K                            # kernel state driven by buy MOs
    R1 = [0.0] * K                            # kernel state driven by sell MOs
    mu, L, th, kap, zs, zb = p.mu, p.lim_rate, p.cancel_rate, p.kappa, p.z_scale, p.z_beta
    p_imp = p.p_imp

    w = place_pmf(p.place_alpha, p.place_d0, p.place_g, p.place_dmax)
    cdf = list(np.cumsum(w))

    book = book if book is not None else Book()
    oid = 0
    msgs = [] if record_messages else None
    ev_t, ev_b, ev_a = array("d"), array("d"), array("d")
    mo_t, mo_s, mo_q, mo_m0, mo_m1 = array("d"), array("d"), array("d"), array("d"), array("d")
    depth = np.zeros((2, depth_levels))
    n_snap = 0

    def lsize(mu_, sg_):
        return max(1, int(round(rng.lognormvariate(mu_, sg_))))

    # initial book
    for d in range(0, 30):
        oid += 1
        sz = lsize(p.lo_mu, p.lo_sigma)
        book.limit(oid, BID, p.p0 - d, sz)
        if msgs is not None:
            msgs.append((0.0, "add", BID, p.p0 - d, sz, oid))
        oid += 1
        sz = lsize(p.lo_mu, p.lo_sigma)
        book.limit(oid, ASK, p.p0 + 1 + d, sz)
        if msgs is not None:
            msgs.append((0.0, "add", ASK, p.p0 + 1 + d, sz, oid))
    last_bb, last_ba = p.p0, p.p0 + 1

    t, z, n = 0.0, 0.0, 0
    while n < n_events:
        c = th * len(book.live)
        lamB = lamS = mu
        for k in range(K):
            lamB += a_same[k] * R0[k] + a_cross[k] * R1[k]
            lamS += a_same[k] * R1[k] + a_cross[k] * R0[k]
        tz = math.tanh(z / zs)
        fa, fb = 1.0 + kap * tz, 1.0 - kap * tz
        bound = lamB + lamS + L * (max(fa, 1.0) + max(fb, 1.0)) + c   # valid: all parts non-increasing in time
        dt = rng.expovariate(bound)
        for k in range(K):
            e = math.exp(-betas[k] * dt)
            R0[k] *= e
            R1[k] *= e
        z *= math.exp(-zb * dt)
        t += dt
        lamB = lamS = mu
        for k in range(K):
            lamB += a_same[k] * R0[k] + a_cross[k] * R1[k]
            lamS += a_same[k] * R1[k] + a_cross[k] * R0[k]
        tz = math.tanh(z / zs)
        fa, fb = 1.0 + kap * tz, 1.0 - kap * tz
        total = lamB + lamS + L * (fa + fb) + c
        u = rng.random() * bound
        if u > total:
            continue

        if u < lamB + lamS:                                   # ---- market order
            side = BID if u < lamB else ASK
            size = lsize(p.mo_mu, p.mo_sigma)
            bb, ba = book.quotes()
            m0 = (bb + ba) / 2 if (bb is not None and ba is not None) else NAN
            fills = book.market(side, size)
            if fills:
                if on_fill is not None:
                    for pr, q, o in fills:
                        on_fill(o, pr, q)
                if msgs is not None:
                    for pr, q, o in fills:
                        msgs.append((t, "exec", -side, pr, q, o))
                bb, ba = book.quotes()
                m1 = (bb + ba) / 2 if (bb is not None and ba is not None) else NAN
                mo_t.append(t); mo_s.append(side); mo_q.append(size); mo_m0.append(m0); mo_m1.append(m1)
            Rt = R0 if side == BID else R1
            for k in range(K):
                Rt[k] += 1.0
            z += side
        elif u < lamB + lamS + L * (fa + fb):                 # ---- limit order
            is_bid = u < lamB + lamS + L * fb
            bb, ba = book.quotes()
            bb = last_bb if bb is None else bb
            ba = last_ba if ba is None else ba
            if ba - bb > 1 and rng.random() < p_imp:                  # improve inside the spread
                price = bb + 1 + int(rng.random() * (ba - bb - 1)) if is_bid else \
                        ba - 1 - int(rng.random() * (ba - bb - 1))
            else:                                                     # behind / at own best
                d = bisect.bisect_left(cdf, rng.random())             # 0-based ticks behind touch
                price = max(1, bb - d) if is_bid else ba + d
            oid += 1
            size = lsize(p.lo_mu, p.lo_sigma)
            book.limit(oid, BID if is_bid else ASK, price, size)
            if msgs is not None:
                msgs.append((t, "add", BID if is_bid else ASK, price, size, oid))
        else:                                                 # ---- cancellation
            N = len(book.live)
            if N:
                o = book.live[int(rng.random() * N)]
                if o > 0:                                  # player orders have negative ids
                    sd, pr, sz = book.orders[o]
                    if msgs is not None:
                        msgs.append((t, "cancel", sd, pr, sz, o))
                    book.cancel(o)

        bb, ba = book.quotes()
        if bb is not None: last_bb = bb
        if ba is not None: last_ba = ba
        ev_t.append(t); ev_b.append(NAN if bb is None else bb); ev_a.append(NAN if ba is None else ba)
        n += 1
        yield t, bb, ba

        if snapshot_every and n % snapshot_every == 0 and bb is not None and ba is not None:
            for sd, pr, sz in book.orders.values():
                dist = (bb - pr) if sd == BID else (pr - ba)
                if 0 <= dist < depth_levels:
                    depth[0 if sd == BID else 1, dist] += sz
            n_snap += 1

    df = None
    if msgs is not None:
        df = pd.DataFrame(msgs, columns=["time", "event", "side", "price", "size", "oid"])
    return Result(np.frombuffer(ev_t, float).copy(), np.frombuffer(ev_b, float).copy(),
                  np.frombuffer(ev_a, float).copy(), np.frombuffer(mo_t, float).copy(),
                  np.frombuffer(mo_s, float).copy(), np.frombuffer(mo_q, float).copy(),
                  np.frombuffer(mo_m0, float).copy(), np.frombuffer(mo_m1, float).copy(),
                  depth / max(n_snap, 1), df)

def simulate(*args, **kwargs):
    """Original behaviour: run to completion and return the Result."""
    gen = _run(*args, **kwargs)
    while True:
        try:
            next(gen)
        except StopIteration as stop:
            return stop.value