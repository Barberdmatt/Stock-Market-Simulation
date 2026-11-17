import asyncio
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .book import Book, BID, ASK
from .model import Params, _run
from .portfolio import Portfolio, STARTING_CASH

START = {"AAPL": 228, "MSFT": 415, "NVDA": 140, "AMZN": 205, "GOOGL": 175,
         "META": 590, "TSLA": 330, "JPM": 240, "COST": 920, "AMD": 140}

pf = Portfolio()
open_orders = {}          # oid -> {"sym", "side": "b"/"s", "q": remaining, "lim": dollars, "t": ms}
next_oid = [0]            # player order ids are negative; the simulator's are positive


def on_fill(oid, px, qty):
    """A resting order was hit. Credit it if it belongs to the player."""
    o = open_orders.get(oid)
    if not o:
        return
    pf.apply_fill(o["sym"], o["side"] == "b", qty, px / 100, "Limit")
    o["q"] -= qty
    if o["q"] <= 0:
        del open_orders[oid]


class Market:
    def __init__(self, sym, price, seed):
        self.sym, self.open = sym, price
        self.book = Book()
        self.gen = _run(Params(p0=int(price * 100)), 10**12, seed=seed,
                        book=self.book, on_fill=on_fill, snapshot_every=0)
        self.hist = deque(maxlen=300)
        for _ in range(50):                    # warm up so the book isn't brand new
            next(self.gen)
        self.record()

    def record(self):
        bb, ba = self.book.quotes()
        if bb is not None and ba is not None:
            self.hist.append((bb + ba) / 200)


markets = {s: Market(s, p, i) for i, (s, p) in enumerate(START.items())}


def top(book, side, n=6):
    lv = book.levels[side]
    return [[p / 100, sum(lv[p].values())] for p in sorted(lv, reverse=(side == BID))[:n]]


def reserved_cash():
    return sum(o["q"] * o["lim"] for o in open_orders.values() if o["side"] == "b")


def reserved_shares(sym):
    return sum(o["q"] for o in open_orders.values() if o["side"] == "s" and o["sym"] == sym)


async def ticker():
    n = 0
    while True:
        for m in markets.values():
            for _ in range(20):                # ~20 simulated events per stock per second
                next(m.gen)
            m.record()
        n += 1
        if n % 5 == 0:
            pf.record_snapshot({s: {"mid": m.hist[-1]} for s, m in markets.items()})
        await asyncio.sleep(1)


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(ticker())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)
# Handlers are `async def` with no awaits, so they never run in the middle of a market step.


@app.get("/api/market")
async def market():
    out = {}
    for s, m in markets.items():
        bb, ba = m.book.quotes()
        if bb is None or ba is None:
            continue
        out[s] = {"open": m.open, "mid": (bb + ba) / 200, "bid": bb / 100, "ask": ba / 100,
                  "sp": (ba - bb) / 100, "bk": [top(m.book, BID), top(m.book, ASK)],
                  "h": list(m.hist)}
    return out


@app.get("/api/account")
async def account():
    value = pf.cash + sum(p["quantity"] * markets[s].hist[-1] for s, p in pf.positions.items())
    return {
        "cash": pf.cash, "bp": pf.cash - reserved_cash(), "equity": value,
        "pos": {s: {"q": p["quantity"], "avg": p["avg_cost"]} for s, p in pf.positions.items()},
        "orders": [{"id": oid, **o} for oid, o in open_orders.items()],
        "hist": pf.trades,
        "eq": [[datetime.fromisoformat(h["timestamp"]).timestamp() * 1000, h["total_value"]]
               for h in pf.history],
    }


class Order(BaseModel):
    sym: str
    side: str                  # "b" or "s"
    qty: int
    type: str = "market"       # "market" or "limit"
    limit: float | None = None


@app.post("/api/order")
async def order(o: Order):
    if o.sym not in markets:
        raise HTTPException(404, "Unknown symbol")
    if not 1 <= o.qty <= 5000:
        raise HTTPException(400, "Order size must be between 1 and 5,000 shares")
    book = markets[o.sym].book
    buy = o.side == "b"
    side = BID if buy else ASK
    have = pf.positions.get(o.sym, {}).get("quantity", 0) - reserved_shares(o.sym)
    if not buy and o.qty > have:
        raise HTTPException(400, "Not enough shares available to sell")
    power = pf.cash - reserved_cash()

    if o.type == "market":
        px = book.preview(side, o.qty)
        if px is None:
            raise HTTPException(400, "Not enough liquidity right now")
        if buy and px * o.qty / 100 > power:
            raise HTTPException(400, "Not enough buying power")
        fills = book.market(side, o.qty)
        kind = "Market"
    else:
        if not o.limit or o.limit <= 0:
            raise HTTPException(400, "Enter a limit price")
        lim = round(o.limit * 100)
        if buy and lim * o.qty / 100 > power:
            raise HTTPException(400, "Not enough buying power")
        next_oid[0] -= 1
        oid = next_oid[0]
        fills = book.limit(oid, side, lim, o.qty)
        left = o.qty - sum(q for _, q, _ in fills)
        if left > 0:
            open_orders[oid] = {"sym": o.sym, "side": o.side, "q": left,
                                "lim": lim / 100, "t": int(datetime.now().timestamp() * 1000)}
        kind = "Limit"

    got = sum(q for _, q, _ in fills)
    for px, q, resting in fills:
        pf.apply_fill(o.sym, buy, q, px / 100, kind)   # the player's side
        on_fill(resting, px, q)                        # the other side, if it was a player order
    avg = sum(px * q for px, q, _ in fills) / got / 100 if got else None
    return {"filled": got, "avg": avg, "resting": o.qty - got if o.type == "limit" else 0}


@app.post("/api/cancel/{oid}")
async def cancel(oid: int):
    o = open_orders.pop(oid, None)
    if o:
        markets[o["sym"]].book.cancel(oid)
    return {"ok": True}


@app.post("/api/reset")
async def reset():
    for oid, o in list(open_orders.items()):
        markets[o["sym"]].book.cancel(oid)
    open_orders.clear()
    pf.cash, pf.positions, pf.realized_profit = STARTING_CASH, {}, 0.0
    pf.history, pf.trades = [], []
    pf.save()
    return {"ok": True}


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")