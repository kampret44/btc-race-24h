# Dip-Buy Mean-Reversion Bot — BTC Race 24h

[![make.fun](https://make.fun/badge/btc-race-24h-20261115-0828.svg)](https://make.fun/bounty/btc-race-24h-20261115-0828)
[![rank](https://make.fun/badge/btc-race-24h-20261115-0828/kampret44/btc-race-24h/rank.svg)](https://make.fun/bounty/btc-race-24h-20261115-0828)
[![reward](https://make.fun/badge/btc-race-24h-20261115-0828/kampret44/btc-race-24h/reward.svg)](https://make.fun/bounty/btc-race-24h-20261115-0828)

Entry for the [make.fun BTC race 24h bounty](https://make.fun/bounty/btc-race-24h-20261115-0828):
one asset (CBBTC vs USDC), $1,000 paper money, long only, no leverage.
The bot races the live 24h window after the deadline.

## Strategy

**Buy deep dips, ride the bounce with a trailing stop.**

The dev window (2026-11-14 08:29 → 2026-11-15 08:28 UTC) fell −4% in a
choppy grind, and plain trend-following loses there (EMA-cross bots:
−$8 to −$26). But sharp drops below the slow average bounce
reliably: on the dev bars, a close 150+ bps below the 120-bar SMA
bounced +113 bps in 30 minutes (82% of cases) and +213 bps in 60
minutes (80%). A full-size round trip costs ~26–44 bps (4 bps fee +
2 bps slippage + price impact per side), so the bot only trades deep,
high-conviction dips and lets the winner run.

- **Entry** (decided on a bar's close, filled at the next open):
  close is ≥ 160 bps below the 120-bar SMA, not holding, not in
  cooldown. Buys the full cash balance (up to 100% of equity).
- **Exit** (the whole position, on a bar's close):
  - *Trailing stop:* once in profit, sell when the close retraces
    50 bps from the highest close since entry.
  - *Hard stop:* sell if the close is 150 bps below the entry fill.
  - *Max hold:* sell after 240 bars (4 hours) in the position.
  - *Cooldown:* 30 bars after any exit before a new entry.

Parameters sit in a plateau, not a sharp peak: dip −150 to −170,
trailing 40–70 bps, SMA 110–140 all give +$30 to +$35 on dev, so the
bot is not tuned to one wiggle of the dev window.

## Local grade (kit CLI, dev window)

| Metric | Value |
|---|---|
| Net PnL | **+$35.06 USDC** |
| Trades | 8 fills (4 round trips, all profitable, win rate 1.00) |
| Max drawdown | 2.20% (guardrail: ≤ 25%) |
| Fees | $3.22 (at 2× fees net PnL still +$31.77) |
| Rejected orders | 0 |
| Guardrails | met (trades, symbols, drawdown) |
| Determinism | L1 regrade reproduced byte for byte |

## Files

- `main.py` — the bot (Python 3.13, stdlib only, deterministic:
  no clock, no environment, no randomness; float64 arithmetic on
  closes the harness sends).
- `vendor/makefun_bars.py` — byte copy of the kit's Python shim
  (`sdk/makefun_bars.py`); the bot runs through `makefun_bars.run`.

## How it works

`main.py` keeps the close history, the entry fill price (taken from
the batch fills the harness reports, so stops use the price actually
paid), the peak close since entry, and the cooldown timer. On each
batch it folds in fills, records the new close, skips orders during
warm-up, then either looks for a dip entry or checks the three exits.
It never orders more than the protocol allows and never holds more
than one position.

## License

MIT — see `LICENSE`.
