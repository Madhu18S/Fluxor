// Friction layer — mirrors fluxor/friction.py
import type { FeeModel, LatencyModel, SlippageModel } from './config'

export interface FrictionBreakdown {
  gross: number
  after_latency: number
  fee_cost: number
  slippage_cost: number
  net: number
  latency_survival: number
}

export function latencySurvival(latency_ms: number, decay_ms: number): number {
  if (latency_ms <= 0) return 1.0
  return Math.exp(-latency_ms / decay_ms)
}

export function applyFriction(
  gross_spread: number,
  fees: FeeModel,
  slippage: SlippageModel,
  latency: LatencyModel,
  latency_ms?: number,
): FrictionBreakdown {
  const lat = latency_ms !== undefined ? latency_ms : latency.round_trip_ms
  const survival = latencySurvival(lat, latency.decay_ms)
  const after_latency = gross_spread * survival

  // 4 legs: open (buy A + sell B) + close (sell A + buy B)
  const fee_cost = 2.0 * (fees.binanceus + fees.coinbase)
  const slippage_cost = 4.0 * slippage.per_leg

  const net = after_latency - fee_cost - slippage_cost
  return { gross: gross_spread, after_latency, fee_cost, slippage_cost, net, latency_survival: survival }
}
