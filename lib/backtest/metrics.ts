// Metrics — mirrors fluxor/metrics.py
import type { BacktestConfig } from './config'
import type { BacktestResult, PriceBar } from './engine'
import { runBacktest } from './engine'

export interface Metrics {
  sharpe: number
  trade_count: number
  win_rate: number
  avg_gross_spread_bps: number
  avg_net_spread_bps: number
  phantom_alpha_pct: number
  max_drawdown_pct: number
  total_net_pnl: number
  total_gross_pnl: number
  final_equity: number
  strategy_uptime_pct: number
}

export interface LatencyPoint {
  latency_ms: number
  sharpe: number
  avg_net_spread_bps: number
  win_rate: number
  total_net_pnl: number
  trade_count: number
}

function annualizedSharpe(
  equity: { ts: number; friction: number }[],
  trading_days: number,
  starting_capital: number,
): number {
  if (equity.length < 2) return 0

  // Build a daily equity map: day -> last equity value seen that day
  const byDay = new Map<string, number>()
  for (const pt of equity) {
    const d = new Date(pt.ts).toISOString().slice(0, 10)
    byDay.set(d, pt.friction)
  }

  // Fill ALL calendar days in the window with carry-forward equity so that
  // flat (no-trade) days contribute zero returns rather than being omitted.
  // Omitting flat days would artificially inflate Sharpe.
  const firstDay = equity[0].ts
  const lastDay = equity[equity.length - 1].ts
  const allDays: string[] = []
  for (let t = firstDay; t <= lastDay; t += 86_400_000) {
    allDays.push(new Date(t).toISOString().slice(0, 10))
  }

  const filled: number[] = []
  let carry = starting_capital
  for (const day of allDays) {
    if (byDay.has(day)) carry = byDay.get(day)!
    filled.push(carry)
  }

  if (filled.length < 2) return 0

  const rets: number[] = []
  for (let i = 1; i < filled.length; i++) {
    const prev = filled[i - 1]
    if (prev > 0) rets.push((filled[i] - prev) / prev)
  }
  if (rets.length < 2) return 0

  const mean = rets.reduce((a, b) => a + b, 0) / rets.length
  const variance = rets.reduce((a, b) => a + (b - mean) ** 2, 0) / (rets.length - 1)
  const sd = Math.sqrt(variance)
  if (sd === 0 || isNaN(sd)) return 0
  return (mean / sd) * Math.sqrt(trading_days)
}

function maxDrawdown(equity: { friction: number }[]): number {
  if (equity.length === 0) return 0
  let peak = -Infinity
  let max_dd = 0
  for (const pt of equity) {
    if (pt.friction > peak) peak = pt.friction
    const dd = (peak - pt.friction) / peak
    if (dd > max_dd) max_dd = dd
  }
  return max_dd
}

export function computeMetrics(result: BacktestResult): Metrics {
  const { trades, equity, config, n_bars } = result

  const sharpe = annualizedSharpe(equity, config.trading_days_per_year, config.starting_capital)

  if (trades.length === 0) {
    return {
      sharpe: 0, trade_count: 0, win_rate: 0,
      avg_gross_spread_bps: 0, avg_net_spread_bps: 0,
      phantom_alpha_pct: 0, max_drawdown_pct: 0,
      total_net_pnl: 0, total_gross_pnl: 0,
      final_equity: equity.length ? equity[equity.length - 1].friction : config.starting_capital,
      strategy_uptime_pct: 100,
    }
  }

  const trade_count = trades.length
  const win_rate = 100 * (trades.filter(t => t.profitable_after_friction).length / trade_count)
  const avg_gross = trades.reduce((a, t) => a + t.gross_spread_bps, 0) / trade_count
  const avg_net = trades.reduce((a, t) => a + t.net_spread_bps, 0) / trade_count
  const phantom = avg_gross !== 0 ? 100 * (1 - avg_net / avg_gross) : 0
  const mdd = 100 * maxDrawdown(equity)
  const total_net = trades.reduce((a, t) => a + t.net_pnl, 0)
  const total_gross = trades.reduce((a, t) => a + t.gross_pnl, 0)

  // Uptime: actual aligned 1-min bars vs expected bars in the window.
  // We use the raw n_bars (inner-joined) against the total possible minutes
  // so gaps where one exchange was missing data lower the score correctly.
  const first = equity[0]?.ts ?? 0
  const last = equity[equity.length - 1]?.ts ?? 0
  const expected_bars = Math.round((last - first) / 60_000) + 1
  const uptime = expected_bars > 0 ? 100 * Math.min(1, n_bars / expected_bars) : 100

  return {
    sharpe,
    trade_count,
    win_rate,
    avg_gross_spread_bps: avg_gross,
    avg_net_spread_bps: avg_net,
    phantom_alpha_pct: phantom,
    max_drawdown_pct: mdd,
    total_net_pnl: total_net,
    total_gross_pnl: total_gross,
    final_equity: equity[equity.length - 1]?.friction ?? config.starting_capital,
    strategy_uptime_pct: uptime,
  }
}

export function latencySensitivity(
  bars: PriceBar[],
  config: BacktestConfig,
): LatencyPoint[] {
  return config.latency_sweep_ms.map(lat => {
    const res = runBacktest(bars, config, lat)
    const m = computeMetrics(res)
    return {
      latency_ms: lat,
      sharpe: m.sharpe,
      avg_net_spread_bps: m.avg_net_spread_bps,
      win_rate: m.win_rate,
      total_net_pnl: m.total_net_pnl,
      trade_count: m.trade_count,
    }
  })
}
