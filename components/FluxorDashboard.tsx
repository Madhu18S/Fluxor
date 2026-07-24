'use client'

import { useState } from 'react'
import { RefreshCw, AlertTriangle, Activity } from 'lucide-react'
import { MetricCard } from './MetricCard'
import { EquityCurveChart } from './EquityCurveChart'
import { LatencyChart } from './LatencyChart'
import { LatencyTable } from './LatencyTable'
import { ResumeBullet } from './ResumeBullet'

interface Metrics {
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

interface LatencyPoint {
  latency_ms: number
  sharpe: number
  avg_net_spread_bps: number
  win_rate: number
  total_net_pnl: number
  trade_count: number
}

interface EquityPoint {
  ts: number
  naive: number
  friction: number
}

interface BacktestData {
  metrics: Metrics
  latencyPoints: LatencyPoint[]
  equity: EquityPoint[]
  n_bars: number
  months: number
  symbol: string
  resumeBullet: string
  window: { start: number; end: number }
}

function fmtDollars(v: number) {
  const abs = Math.abs(v)
  const sign = v < 0 ? '-' : '+'
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(2)}M`
  if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(1)}k`
  return `${sign}$${abs.toFixed(0)}`
}

export function FluxorDashboard() {
  const [months, setMonths] = useState(3)
  const [data, setData] = useState<BacktestData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [progress, setProgress] = useState('')

  async function runBacktest() {
    setLoading(true)
    setError(null)
    setData(null)
    setProgress('Fetching 1-minute data from Binance.US + Coinbase…')

    try {
      const resp = await fetch(`/api/backtest?months=${months}&symbol=BTC-USD`)
      const json = await resp.json()
      if (!resp.ok) throw new Error(json.error ?? `HTTP ${resp.status}`)
      setData(json as BacktestData)
      setProgress('')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
      setProgress('')
    } finally {
      setLoading(false)
    }
  }

  const m = data?.metrics

  return (
    <div className="min-h-screen bg-background text-foreground font-mono">
      {/* Header */}
      <header className="border-b border-border px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between flex-wrap gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-semibold tracking-wide text-cyan">
                FLUXOR
              </h1>
              <span className="text-xs border border-amber/40 text-amber px-1.5 py-0.5 rounded tracking-wider uppercase">
                CEX-CEX Module
              </span>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              friction-aware statistical arb &nbsp;·&nbsp; Binance.US ↔ Coinbase &nbsp;·&nbsp; BTC-USD spot &nbsp;·&nbsp; 1-min bars
            </p>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-2">
              <label className="text-xs text-muted-foreground">Window</label>
              <select
                value={months}
                onChange={e => setMonths(Number(e.target.value))}
                disabled={loading}
                className="text-xs bg-surface border border-border rounded px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-cyan"
              >
                {[1, 2, 3, 6].map(n => (
                  <option key={n} value={n}>{n} month{n > 1 ? 's' : ''}</option>
                ))}
              </select>
            </div>

            <button
              onClick={runBacktest}
              disabled={loading}
              className="flex items-center gap-2 text-xs bg-cyan text-background px-4 py-1.5 rounded font-semibold tracking-wider uppercase transition-opacity hover:opacity-80 disabled:opacity-40"
            >
              <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
              {loading ? 'Running…' : 'Run Backtest'}
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        {/* Loading state */}
        {loading && (
          <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-4">
            <Activity className="w-4 h-4 text-cyan animate-pulse" />
            <span className="text-sm text-muted-foreground">{progress}</span>
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="flex items-start gap-3 rounded-lg border border-loss/40 bg-loss/10 p-4">
            <AlertTriangle className="w-4 h-4 text-loss mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm font-semibold text-loss">Backtest failed</p>
              <p className="text-xs text-muted-foreground mt-1">{error}</p>
            </div>
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && !data && (
          <div className="flex flex-col items-center justify-center py-24 gap-4 text-center">
            <div className="w-12 h-12 rounded-full border border-cyan/20 flex items-center justify-center">
              <Activity className="w-5 h-5 text-cyan/50" />
            </div>
            <div>
              <p className="text-sm font-semibold text-foreground">No backtest run yet</p>
              <p className="text-xs text-muted-foreground mt-1 max-w-sm leading-relaxed">
                Click &ldquo;Run Backtest&rdquo; to fetch real 1-minute historical data from the public
                Binance.US and Coinbase REST APIs and compute the full metrics suite.
              </p>
              <p className="text-xs text-muted-foreground/60 mt-2">
                A 3-month run fetches ~130k bars and takes 30–90s.
              </p>
            </div>
          </div>
        )}

        {/* Results */}
        {data && m && (
          <>
            {/* Window info */}
            <div className="text-xs text-muted-foreground flex flex-wrap gap-4">
              <span>
                Window: {new Date(data.window.start).toISOString().slice(0, 10)} →{' '}
                {new Date(data.window.end).toISOString().slice(0, 10)}
              </span>
              <span>Aligned bars: {data.n_bars.toLocaleString()}</span>
              <span>Trades: {m.trade_count.toLocaleString()}</span>
            </div>

            {/* Headline metrics */}
            <section>
              <h2 className="text-xs tracking-widest text-muted-foreground uppercase mb-3">
                Headline Metrics &nbsp;(friction-adjusted)
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
                <MetricCard
                  label="Sharpe (ann.)"
                  value={m.sharpe.toFixed(2)}
                  sub="risk-free = 0"
                  highlight={m.sharpe > 1 ? 'gain' : m.sharpe > 0 ? 'cyan' : 'loss'}
                />
                <MetricCard
                  label="Win Rate"
                  value={`${m.win_rate.toFixed(1)}%`}
                  sub={`of ${m.trade_count.toLocaleString()} trades`}
                  highlight="amber"
                />
                <MetricCard
                  label="Max Drawdown"
                  value={`${m.max_drawdown_pct.toFixed(2)}%`}
                  sub="peak-to-trough"
                  highlight={m.max_drawdown_pct > 10 ? 'loss' : 'muted'}
                />
                <MetricCard
                  label="Net PnL"
                  value={fmtDollars(m.total_net_pnl)}
                  sub={`from $100k capital`}
                  highlight={m.total_net_pnl >= 0 ? 'gain' : 'loss'}
                />
                <MetricCard
                  label="Uptime"
                  value={`${m.strategy_uptime_pct.toFixed(0)}%`}
                  sub="aligned data coverage"
                  highlight="muted"
                />
              </div>
            </section>

            {/* Spread capture */}
            <section>
              <h2 className="text-xs tracking-widest text-muted-foreground uppercase mb-3">
                Spread Capture &mdash; The Differentiator
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <MetricCard
                  label="Avg gross spread"
                  value={`${m.avg_gross_spread_bps.toFixed(2)} bps`}
                  sub="naive book"
                  highlight="muted"
                />
                <MetricCard
                  label="Avg net spread"
                  value={`${m.avg_net_spread_bps.toFixed(2)} bps`}
                  sub="after friction"
                  highlight={m.avg_net_spread_bps > 0 ? 'gain' : 'loss'}
                />
                <MetricCard
                  label="Phantom alpha"
                  value={`${m.phantom_alpha_pct.toFixed(1)}%`}
                  sub="gross spread destroyed"
                  highlight="amber"
                />
                <MetricCard
                  label="Gross PnL"
                  value={fmtDollars(m.total_gross_pnl)}
                  sub="naive (unrealizable)"
                  highlight="muted"
                />
              </div>
            </section>

            {/* Equity curve */}
            <section>
              <h2 className="text-xs tracking-widest text-muted-foreground uppercase mb-3">
                Equity Curve &mdash; Naive vs Friction-Adjusted
              </h2>
              <div className="rounded-lg border border-border bg-card p-4">
                <EquityCurveChart data={data.equity} />
              </div>
            </section>

            {/* Latency sensitivity */}
            <section>
              <h2 className="text-xs tracking-widest text-muted-foreground uppercase mb-3">
                Latency Sensitivity &mdash; Edge Decay Model
              </h2>
              <div className="grid lg:grid-cols-2 gap-4">
                <div className="rounded-lg border border-border bg-card p-4">
                  <LatencyChart data={data.latencyPoints} />
                </div>
                <LatencyTable data={data.latencyPoints} />
              </div>
            </section>

            {/* Resume bullet */}
            <section>
              <h2 className="text-xs tracking-widest text-muted-foreground uppercase mb-3">
                Resume Bullet &mdash; Numbers Filled In
              </h2>
              <ResumeBullet text={data.resumeBullet} />
            </section>

            {/* Config footnote */}
            <section className="text-xs text-muted-foreground/60 leading-relaxed border-t border-border/50 pt-4">
              <strong className="text-muted-foreground">Backtest config:</strong>{' '}
              Fees: 1bp/leg Binance.US + 1bp/leg Coinbase (VIP tier) &bull;
              Slippage: 0.5bp/leg (4 legs/round-trip) &bull;
              Latency decay: exp(&minus;ms/50ms) applied as fill-survival probability &bull;
              Entry: 15bps deviation from 120-min rolling basis &bull;
              Exit: 3bps convergence &bull;
              Max hold: 120min &bull;
              Notional: $10k/trade &bull;
              Capital: $100k &bull;
              Sharpe uses carry-forward daily equity so flat days contribute zero return
            </section>

            {/* Project scope note */}
            <section className="rounded-lg border border-border/60 bg-surface-2/40 p-4 text-xs leading-relaxed space-y-2">
              <p className="text-muted-foreground font-semibold tracking-wide uppercase text-[10px]">
                Full Project Scope (CEX-CEX module shown above)
              </p>
              <ul className="text-muted-foreground/80 space-y-1 list-none">
                <li><span className="text-gain mr-2">+</span>CEX-CEX stat arb (Binance.US ↔ Coinbase) &mdash; <em>this dashboard, real numbers</em></li>
                <li><span className="text-muted-foreground/40 mr-2">·</span>Triangular arb + Uniswap v3 DEX pool integration &mdash; Python asyncio/websockets L2 reconstruction</li>
                <li><span className="text-muted-foreground/40 mr-2">·</span>Gamma-distributed latency anomaly injection into the friction layer (stochastic, not deterministic decay)</li>
                <li><span className="text-muted-foreground/40 mr-2">·</span>Q-learning SOR optimizer minimizing market impact / adverse selection across multi-asset loops</li>
              </ul>
              <p className="text-muted-foreground/50 text-[10px]">
                The metrics above reflect only the CEX-CEX component. Do not cite the DEX, asyncio, or RL modules on your resume unless you have working Python code for those.
              </p>
            </section>
          </>
        )}
      </main>
    </div>
  )
}
