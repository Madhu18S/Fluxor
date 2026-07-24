// Data layer — fetches real 1-minute OHLCV from Binance.US and Coinbase
// Mirrors fluxor/data.py but runs in Next.js API routes
import type { PriceBar } from './engine'

// ─── Binance.US ────────────────────────────────────────────────────────────

async function fetchBinanceus(
  symbol: string,
  startMs: number,
  endMs: number,
): Promise<Map<number, number>> {
  // BTC-USD -> BTCUSDT for Binance.US
  const sym = symbol.replace('-', '').replace('BTCUSD', 'BTCUSDT')
  const map = new Map<number, number>()
  let cursor = startMs

  while (cursor < endMs) {
    const url = new URL('https://api.binance.us/api/v3/klines')
    url.searchParams.set('symbol', sym)
    url.searchParams.set('interval', '1m')
    url.searchParams.set('startTime', String(cursor))
    url.searchParams.set('endTime', String(endMs))
    url.searchParams.set('limit', '1000')

    const resp = await fetch(url.toString(), {
      headers: { 'User-Agent': 'fluxor-backtest/1.0' },
      signal: AbortSignal.timeout(30_000),
    })
    if (!resp.ok) throw new Error(`Binance.US ${resp.status}: ${await resp.text()}`)
    const batch: unknown[][] = await resp.json()
    if (!batch.length) break

    for (const k of batch) {
      const ts = Number(k[0])
      const close = parseFloat(k[4] as string)
      map.set(ts, close)
    }
    const last = Number(batch[batch.length - 1][0])
    cursor = last + 60_000
    if (batch.length < 1000) break
    // Small pause to respect public rate limit
    await new Promise(r => setTimeout(r, 150))
  }
  return map
}

// ─── Coinbase ──────────────────────────────────────────────────────────────

async function fetchCoinbase(
  symbol: string,
  startMs: number,
  endMs: number,
): Promise<Map<number, number>> {
  const product = symbol.includes('-') ? symbol : 'BTC-USD'
  const map = new Map<number, number>()
  const step = 300 * 60_000 // 300 min in ms
  let cursor = startMs

  while (cursor < endMs) {
    const chunkEnd = Math.min(cursor + step, endMs)
    const url = new URL(`https://api.exchange.coinbase.com/products/${product}/candles`)
    url.searchParams.set('granularity', '60')
    url.searchParams.set('start', String(Math.floor(cursor / 1000)))
    url.searchParams.set('end', String(Math.floor(chunkEnd / 1000)))

    const resp = await fetch(url.toString(), {
      headers: { 'User-Agent': 'fluxor-backtest/1.0' },
      signal: AbortSignal.timeout(30_000),
    })
    if (!resp.ok) throw new Error(`Coinbase ${resp.status}: ${await resp.text()}`)
    const batch: number[][] = await resp.json()

    for (const c of batch) {
      const ts = c[0] * 1000 // s -> ms
      const close = c[4]
      map.set(ts, close)
    }
    cursor = chunkEnd
    await new Promise(r => setTimeout(r, 200))
  }
  return map
}

// ─── Public API ────────────────────────────────────────────────────────────

export async function loadPair(
  symbol: string,
  months: number,
): Promise<PriceBar[]> {
  const endMs = Date.now()
  const startMs = endMs - months * 30 * 24 * 60 * 60_000

  const [aMap, bMap] = await Promise.all([
    fetchBinanceus(symbol, startMs, endMs),
    fetchCoinbase(symbol, startMs, endMs),
  ])

  // Inner join on timestamp
  const bars: PriceBar[] = []
  for (const [ts, price_a] of aMap) {
    const price_b = bMap.get(ts)
    if (price_b !== undefined && price_a > 0 && price_b > 0) {
      bars.push({ ts, price_a, price_b })
    }
  }
  bars.sort((a, b) => a.ts - b.ts)
  return bars
}
