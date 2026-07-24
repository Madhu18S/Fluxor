import { type NextRequest, NextResponse } from 'next/server'
import { defaultConfig, feesForTier, type CoinbaseTier } from '@/lib/backtest/config'
import { loadPair } from '@/lib/backtest/data'
import { runBacktest } from '@/lib/backtest/engine'
import { computeMetrics, latencySensitivity } from '@/lib/backtest/metrics'

// Allow up to 5 minutes for a full 3-month fetch + backtest
export const maxDuration = 300

const VALID_TIERS: CoinbaseTier[] = ['under_10k', '10k_to_50k', '50k_to_100k', '100k_to_1m']

export async function GET(req: NextRequest) {
  const sp = req.nextUrl.searchParams
  const months = Math.min(6, Math.max(1, parseInt(sp.get('months') ?? '3', 10)))
  const symbol = sp.get('symbol') ?? 'BTC-USD'
  const tierParam = sp.get('coinbaseTier') as CoinbaseTier | null
  const coinbaseTier: CoinbaseTier = tierParam && VALID_TIERS.includes(tierParam) ? tierParam : 'under_10k'

  const config = defaultConfig({ months, fees: feesForTier(coinbaseTier) })

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

    // Resume bullet — only claim a Sharpe/phantom-alpha win if the strategy
    // actually cleared friction. Publishing a positive-sounding bullet for a
    // net-negative strategy is exactly the kind of thing that falls apart
    // under a "walk me through the numbers" follow-up.
    const fast = latencyPoints.reduce((a, b) => (a.latency_ms < b.latency_ms ? a : b))
    const slow = latencyPoints.reduce((a, b) => (a.latency_ms > b.latency_ms ? a : b))

    const resumeBullet = metrics.strategy_profitable_after_friction
      ? `Backtested across ${months} months of Binance.US/Coinbase historical 1-minute data, ` +
        `achieving a ${metrics.sharpe.toFixed(1)} Sharpe ratio and ` +
        `${metrics.strategy_uptime_pct.toFixed(0)}% data uptime after accounting ` +
        `for simulated latency and slippage, with friction eliminating ` +
        `${metrics.phantom_alpha_pct.toFixed(0)}% of the naive (zero-friction) spread ` +
        `(Sharpe moves from ${fast.sharpe.toFixed(1)} at ${fast.latency_ms.toFixed(0)}ms to ` +
        `${slow.sharpe.toFixed(1)} at ${slow.latency_ms.toFixed(0)}ms, demonstrating the ` +
        `microstructure model's sensitivity to execution speed).`
      : `Backtested a cross-exchange Binance.US/Coinbase mean-reversion strategy across ${months} ` +
        `months of 1-minute data with a full microstructural friction layer (Gamma-distributed latency, ` +
        `real fee tiers, order-book slippage); found the naive ${metrics.avg_gross_spread_bps.toFixed(1)}bps ` +
        `average edge is fully consumed by friction (net ${metrics.avg_net_spread_bps.toFixed(1)}bps), ` +
        `correctly identifying the strategy as unviable at retail fee tiers rather than reporting phantom alpha.`

    return NextResponse.json({
      metrics,
      latencyPoints,
      equity: result.equity,
      trades: result.trades.slice(0, 500), // cap to 500 rows for payload size
      n_bars: result.n_bars,
      months,
      symbol,
      coinbaseTier,
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
