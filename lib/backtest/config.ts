// Central configuration — mirrors fluxor/config.py

export interface FeeModel {
  binanceus: number // fraction per leg (1 bp = 0.0001)
  coinbase: number
}

export interface LatencyModel {
  round_trip_ms: number
  decay_ms: number
}

export interface SlippageModel {
  per_leg: number // fraction per leg
}

export interface StrategyConfig {
  basis_window_min: number
  entry_threshold_bps: number
  exit_threshold_bps: number
  max_hold_min: number
  notional_per_trade: number
}

export interface BacktestConfig {
  months: number
  starting_capital: number
  fees: FeeModel
  latency: LatencyModel
  slippage: SlippageModel
  strategy: StrategyConfig
  latency_sweep_ms: number[]
  trading_days_per_year: number
}

export const MINUTES_PER_YEAR = 60 * 24 * 365

// ─── Real-world fee schedules (approximate, as of mid-2026 — CHECK CURRENT
// RATES BEFORE PUBLISHING ANY NUMBER, exchanges revise these regularly) ───
//
// Coinbase Advanced Trade taker fee is volume-tiered on trailing 30-day USD
// volume. Most retail accounts sit in the bottom tier and pay the full rate.
// Binance.US taker is comparatively flat for retail-sized accounts.
export const COINBASE_TAKER_FEE_BPS_BY_TIER = {
  under_10k: 60,      // Tier 1 — most retail accounts land here
  '10k_to_50k': 40,   // Tier 2
  '50k_to_100k': 25,  // Tier 3
  '100k_to_1m': 20,   // Tier 4
} as const
export type CoinbaseTier = keyof typeof COINBASE_TAKER_FEE_BPS_BY_TIER

export const BINANCEUS_TAKER_FEE_BPS = 10 // ~0.10% flat retail taker rate

export function feesForTier(coinbaseTier: CoinbaseTier = 'under_10k'): FeeModel {
  return {
    binanceus: BINANCEUS_TAKER_FEE_BPS / 1e4,
    coinbase: COINBASE_TAKER_FEE_BPS_BY_TIER[coinbaseTier] / 1e4,
  }
}

export function defaultConfig(overrides?: Partial<BacktestConfig>): BacktestConfig {
  return {
    months: 3,
    starting_capital: 100_000,
    // Defaults to the fee tier almost every individual trader is actually
    // in (<$10k/mo volume) — override with feesForTier(...) if you trade
    // enough volume to genuinely qualify for a lower Coinbase tier.
    fees: feesForTier('under_10k'),
    latency: { round_trip_ms: 10, decay_ms: 50 },
    // BTC/USD top-of-book spread on liquid venues typically runs ~1-5bps;
    // 3bps/leg is a reasonable, still-conservative default (was 0.5bp).
    slippage: { per_leg: 0.0003 },
    strategy: {
      basis_window_min: 120,
      entry_threshold_bps: 15,
      exit_threshold_bps: 3,
      max_hold_min: 120,
      notional_per_trade: 10_000,
    },
    latency_sweep_ms: [1, 10, 25, 50, 100, 250],
    trading_days_per_year: 365,
    ...overrides,
  }
}
