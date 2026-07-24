// Backtest engine — mirrors fluxor/engine.py
import type { BacktestConfig } from './config'
import { applyFriction } from './friction'

export interface PriceBar {
  ts: number    // unix ms
  price_a: number
  price_b: number
}

export interface Trade {
  entry_time: number
  exit_time: number
  hold_minutes: number
  direction: 'long_A_short_B' | 'short_A_long_B'
  entry_dev_bps: number
  exit_dev_bps: number
  gross_spread_bps: number
  net_spread_bps: number
  fee_cost_bps: number
  slippage_cost_bps: number
  latency_survival: number
  gross_pnl: number
  net_pnl: number
  profitable_after_friction: boolean
}

export interface EquityPoint {
  ts: number
  naive: number
  friction: number
}

export interface BacktestResult {
  trades: Trade[]
  equity: EquityPoint[]   // one per bar
  config: BacktestConfig
  n_bars: number
}

// Rolling mean of a window — returns NaN until window is full
function rollingMean(arr: number[], idx: number, window: number): number {
  if (idx < window - 1) return NaN
  let sum = 0
  for (let i = idx - window + 1; i <= idx; i++) sum += arr[i]
  return sum / window
}

export function runBacktest(
  bars: PriceBar[],
  config: BacktestConfig,
  latency_ms?: number,
): BacktestResult {
  const s = config.strategy
  const n = bars.length

  // Compute basis_bps array
  const basis: number[] = new Array(n)
  for (let i = 0; i < n; i++) {
    basis[i] = ((bars[i].price_b - bars[i].price_a) / bars[i].price_a) * 1e4
  }

  const trades: Trade[] = []
  const pnl_naive = new Float64Array(n)
  const pnl_friction = new Float64Array(n)

  let capital = config.starting_capital
  let in_pos = false
  let direction = 0
  let entry_dev = 0
  let entry_i = 0

  for (let i = 0; i < n; i++) {
    const mean_basis = rollingMean(basis, i, s.basis_window_min)
    if (isNaN(mean_basis)) continue

    const dev = basis[i] - mean_basis

    if (!in_pos) {
      if (Math.abs(dev) >= s.entry_threshold_bps) {
        in_pos = true
        direction = dev > 0 ? 1 : -1
        entry_dev = dev
        entry_i = i
      }
      continue
    }

    const held = i - entry_i
    if (Math.abs(dev) <= s.exit_threshold_bps || held >= s.max_hold_min) {
      const exit_dev = dev
      const gross_frac = (direction * (entry_dev - exit_dev)) / 1e4

      const fb = applyFriction(
        gross_frac,
        config.fees,
        config.slippage,
        config.latency,
        latency_ms,
      )

      const size = Math.min(s.notional_per_trade, capital)
      const gross_dollars = gross_frac * size

      // Latency survival gates whether the fill actually executes:
      // if the market has moved against us by the time our order arrives,
      // we model the effective filled spread as gross * survival rather than
      // scaling after-the-fact. Then fees/slippage apply on top.
      // This means high latency can turn a winning signal into a net loser
      // even if gross spread was positive — the core of the microstructure model.
      const net_dollars = fb.net * size
      capital += net_dollars

      pnl_naive[i] += gross_dollars
      pnl_friction[i] += net_dollars

      trades.push({
        entry_time: bars[entry_i].ts,
        exit_time: bars[i].ts,
        hold_minutes: held,
        direction: direction > 0 ? 'long_A_short_B' : 'short_A_long_B',
        entry_dev_bps: entry_dev,
        exit_dev_bps: exit_dev,
        gross_spread_bps: gross_frac * 1e4,
        net_spread_bps: fb.net * 1e4,
        fee_cost_bps: fb.fee_cost * 1e4,
        slippage_cost_bps: fb.slippage_cost * 1e4,
        latency_survival: fb.latency_survival,
        gross_pnl: gross_dollars,
        net_pnl: net_dollars,
        profitable_after_friction: net_dollars > 0,
      })

      in_pos = false
      direction = 0
    }
  }

  // Build equity curve
  const cap0 = config.starting_capital
  const equity: EquityPoint[] = []
  let cum_naive = 0
  let cum_friction = 0
  // Downsample to at most 2000 points for the chart
  const step = Math.max(1, Math.floor(n / 2000))
  for (let i = 0; i < n; i++) {
    cum_naive += pnl_naive[i]
    cum_friction += pnl_friction[i]
    if (i % step === 0 || i === n - 1) {
      equity.push({
        ts: bars[i].ts,
        naive: cap0 + cum_naive,
        friction: cap0 + cum_friction,
      })
    }
  }

  return { trades, equity, config, n_bars: n }
}
