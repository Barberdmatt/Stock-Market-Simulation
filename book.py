"""Limit order book with strict price-time priority.

Prices are integer ticks. Side: +1 = bid (buy), -1 = ask (sell).
Per price level orders sit in an OrderedDict (FIFO), so cancel is O(1);
best price is found with a heap + lazy deletion. `live`/`pos` allow O(1)
uniform sampling of a resting order (needed for the cancellation model).
"""
import heapq
from collections import OrderedDict

BID, ASK = 1, -1


class Book:
    def __init__(self):
        self.levels = {BID: {}, ASK: {}}      # price -> OrderedDict(oid -> size)
        self.heaps = {BID: [], ASK: []}       # bids store -price
        self.orders = {}                      # oid -> [side, price, size]
        self.live = []                        # list of resting oids
        self.pos = {}                         # oid -> index in `live`

    # ---- queries -----------------------------------------------------
    def best(self, side):
        h, lv = self.heaps[side], self.levels[side]
        if side == BID:
            while h:
                p = -h[0]
                if p in lv:
                    return p
                heapq.heappop(h)
        else:
            while h:
                p = h[0]
                if p in lv:
                    return p
                heapq.heappop(h)
        return None

    def quotes(self):
        return self.best(BID), self.best(ASK)

    # ---- internals ---------------------------------------------------
    def _rest(self, oid, side, price, size):
        lv = self.levels[side]
        q = lv.get(price)
        if q is None:
            q = lv[price] = OrderedDict()
            h = self.heaps[side]
            if len(h) > 8 * len(lv) + 2000:           # purge stale heap entries
                h[:] = [(-p if side == BID else p) for p in lv if p != price]
                heapq.heapify(h)
            heapq.heappush(h, -price if side == BID else price)
        q[oid] = size
        self.orders[oid] = [side, price, size]
        self.pos[oid] = len(self.live)
        self.live.append(oid)

    def _drop(self, oid):
        side, price, _ = self.orders.pop(oid)
        lv = self.levels[side]
        q = lv[price]
        del q[oid]
        if not q:
            del lv[price]
        i = self.pos.pop(oid)
        last = self.live.pop()
        if last != oid:
            self.live[i] = last
            self.pos[last] = i

    def _match(self, side, qty, limit=None):
        """Aggressor `side` consumes the opposite book. Returns (fills, unfilled)."""
        opp, fills, lv = -side, [], self.levels[-side]
        while qty > 0:
            p = self.best(opp)
            if p is None:
                break
            if limit is not None and ((side == BID and p > limit) or (side == ASK and p < limit)):
                break
            q = lv[p]
            while q and qty > 0:
                oid = next(iter(q))
                o = self.orders[oid]
                sz = o[2]
                if sz <= qty:
                    qty -= sz
                    fills.append((p, sz, oid))
                    self._drop(oid)
                else:
                    o[2] = q[oid] = sz - qty          # partial fill keeps queue position
                    fills.append((p, qty, oid))
                    qty = 0
        return fills, qty

    # ---- public order entry ------------------------------------------
    def market(self, side, qty):
        """Returns list of fills (price, qty, resting_oid). Unfilled remainder is dropped."""
        return self._match(side, qty)[0]

    def limit(self, oid, side, price, size):
        """Marketable portion trades immediately, remainder rests. Returns fills."""
        fills, rem = self._match(side, size, limit=price)
        if rem > 0:
            self._rest(oid, side, price, rem)
        return fills

    def cancel(self, oid):
        if oid in self.orders:
            self._drop(oid)
            return True
        return False

    # ---- replay helpers (apply exchange messages without matching) ----
    def insert(self, oid, side, price, size):
        if oid not in self.orders:
            self._rest(oid, side, price, size)

    def reduce(self, oid, size):
        """Reduce a resting order (partial cancel/execution). True if order removed."""
        o = self.orders.get(oid)
        if o is None:
            return None                                # unknown order
        if size >= o[2]:
            self._drop(oid)
            return True
        o[2] -= size
        self.levels[o[0]][o[1]][oid] = o[2]
        return False
