import { type NextRequest, NextResponse } from 'next/server'
import { defaultConfig } from '@/lib/backtest/config'
import { loadPair } from '@/lib/backtest/data'
import { runBacktest } from '@/lib/backtest/engine'
import { computeMetrics, latencySensitivity } from '@/lib/backtest/metrics'

// Allow up to 5 minutes for a full 3-month fetch + backtest
export const maxDuration = 300

export async function GET(req: NextRequest) {
  const sp = req.nextUrl.searchParams
  const months = Math.min(6, Math.max(1, parseInt(sp.get('months') ?? '3', 10)))
  const symbol = sp.get('symbol') ?? 'BTC-USD'

  const config = defaultConfig({ months })

  try {
    const bars = await loadPair(symbol, months)

    if (bars.length < 200) {
      return NextResponse.json(
        { error: `Only ${bars.length} overlapping bars — not enough data.` },
        { status: 422 },
      )
    }

    const result = runBacktest(bars, config)
    const metrics = computeMetrics(result)
    const latencyPoints = latencySensitivity(bars, config)

    // Resume bullet
    const fast = latencyPoints.reduce((a, b) => (a.latency_ms < b.latency_ms ? a : b))
    const slow = latencyPoints.reduce((a, b) => (a.latency_ms > b.latency_ms ? a : b))
    const resumeBullet =
      `Backtested across ${months} months of Binance.US/Coinbase historical 1-minute data, ` +
      `achieving a ${metrics.sharpe.toFixed(1)} Sharpe ratio and ` +
      `${metrics.strategy_uptime_pct.toFixed(0)}% strategy uptime after accounting ` +
      `for simulated latency and slippage, reducing phantom alpha by ` +
      `${metrics.phantom_alpha_pct.toFixed(0)}% versus a naive backtest ` +
      `(Sharpe collapses from ${fast.sharpe.toFixed(1)} at ${fast.latency_ms.toFixed(0)}ms to ` +
      `${slow.sharpe.toFixed(1)} at ${slow.latency_ms.toFixed(0)}ms, demonstrating the ` +
      `microstructure model's sensitivity to execution speed).`

    return NextResponse.json({
      metrics,
      latencyPoints,
      equity: result.equity,
      trades: result.trades.slice(0, 500), // cap to 500 rows for payload size
      n_bars: result.n_bars,
      months,
      symbol,
      resumeBullet,
      window: {
        start: bars[0].ts,
        end: bars[bars.length - 1].ts,
      },
    })
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err)
    console.error('[backtest]', message)
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
