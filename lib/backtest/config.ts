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

export function defaultConfig(overrides?: Partial<BacktestConfig>): BacktestConfig {
  return {
    months: 3,
    starting_capital: 100_000,
    fees: { binanceus: 0.00010, coinbase: 0.00010 },
    latency: { round_trip_ms: 10, decay_ms: 50 },
    slippage: { per_leg: 0.00005 },
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
