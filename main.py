"""Dip-buy mean-reversion bot for the make.fun BTC race (btc-race-24h-20261115-0828).

Strategy (long only, one asset CBBTC vs USDC, start $1,000):
  The dev window fell -4% in a choppy grind, but sharp drops below the
  slow average reliably bounce: on the dev bars, a close 150+ bps below
  the 120-bar SMA bounced +113 bps in 30 min (82% of cases) and +213 bps
  in 60 min (80%). A full-size round trip costs ~26-44 bps (4 bps fee
  + 2 bps slippage + price impact per side), so the bot only trades
  deep, high-conviction dips and rides the bounce with a trailing stop.

  Entry (on a bar's close, filled at the next open):
    close <= SMA(120) * (1 - 160 bps), and not holding, and not in
    cooldown. Buys the full cash balance (up to 100% of equity).

  Exit (the whole position, on a bar's close):
    - Trailing stop: once in profit, sell when the close retraces
      50 bps from the highest close since entry.
    - Hard stop: sell if the close is 150 bps below the entry fill.
    - Max hold: sell after 240 bars (4 hours) in the position.
    - Cooldown: 30 bars after any exit before a new entry.

  All arithmetic is float64 (IEEE 754, deterministic) on closes the
  harness sent; no clock, no environment, no randomness. The bot
  tracks its entry fill price from the batch fills the harness
  reports, so the stop and trailing levels use the price actually
  paid, not the decision close.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bars

SYMBOL = "CBBTC"
SMA_BARS = 120
DIP_BPS = 160          # buy when close is this far below the SMA (bps)
TRAIL_BPS = 50         # sell on this retrace from the peak close, once in profit
STOP_BPS = 150         # hard stop below the entry fill (bps)
MAX_HOLD_BARS = 240    # max bars to hold a position
COOLDOWN_BARS = 30     # bars to wait after an exit before re-entering
MAX_SLIPPAGE_BPS = 100

# --- state (module level; rebuilt deterministically from the batches) ---
closes = []            # closes seen, oldest first (floats)
entry_price = None     # fill price of the open position (float), else None
entry_seq = -1         # seq of the batch whose fill opened the position
peak = None            # highest close since entry (float), else None
cool_until = -1        # do not enter before this seq


def sma(n):
    """Mean of the last n closes, or None before n bars."""
    if len(closes) < n:
        return None
    return sum(closes[-n:]) / n


def on_batch(state, batch):
    global entry_price, entry_seq, peak, cool_until

    # 1) Fold in this batch's fills: a buy fill opens the position and
    #    sets the entry price; a sell fill closes it.
    for fill in batch.get("fills", []):
        if fill.get("symbol") != SYMBOL:
            continue
        status = fill.get("status")
        if status != "filled":
            continue
        if fill.get("side") == "buy":
            entry_price = float(fill["price"])
            entry_seq = state.seq
            peak = entry_price
        elif fill.get("side") == "sell":
            entry_price = None
            entry_seq = -1
            peak = None

    # 2) Record this bar's close.
    bar = None
    for b in batch.get("bars", []):
        if b.get("symbol") == SYMBOL:
            bar = b
            break
    if bar is None:
        return []
    close = float(bar["c"])
    closes.append(close)

    # 3) Warm-up bars: no orders (the harness would reject them).
    if state.warming_up:
        return []

    held = state.positions.get(SYMBOL)
    if held is not None and entry_price is None:
        # Position exists but we missed its fill (e.g. it opened before
        # this run's first batch we saw); use its cost as the entry
        # reference so the exits still work. cost is in quote units;
        # approximate the entry price from the position value at cost.
        # Fall back to the current close so we do not sell immediately.
        entry_price = close
        entry_seq = state.seq
        peak = close

    if held is None:
        # Not holding: look for a dip entry.
        entry_price = None
        entry_seq = -1
        peak = None
        if state.seq < cool_until:
            return []
        s = sma(SMA_BARS)
        if s is None:
            return []
        if (close / s - 1.0) * 10000.0 <= -DIP_BPS:
            notional = state.cash
            if notional <= 0:
                return []
            return [{
                "side": "buy",
                "symbol": SYMBOL,
                "notional_quote_units": notional,
                "max_slippage_bps": MAX_SLIPPAGE_BPS,
            }]
        return []

    # Holding: track the peak and check the exits.
    if peak is None or close > peak:
        peak = close
    ret_bps = (close / entry_price - 1.0) * 10000.0
    retrace_bps = (peak / close - 1.0) * 10000.0
    sell = False
    if ret_bps > 0 and retrace_bps >= TRAIL_BPS:
        sell = True
    elif ret_bps <= -STOP_BPS:
        sell = True
    elif entry_seq >= 0 and (state.seq - entry_seq) >= MAX_HOLD_BARS:
        sell = True
    if sell:
        cool_until = state.seq + COOLDOWN_BARS
        return [{
            "side": "sell",
            "symbol": SYMBOL,
            "qty": held.qty,
            "max_slippage_bps": MAX_SLIPPAGE_BPS,
        }]
    return []


makefun_bars.run(on_batch)
