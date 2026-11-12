// LeakBench metamorphic oracle for Fluxor.
// Invariant: changing bars AFTER cutoff k must not change anything observable at or before k.
// Adjust the import path and the two TODO accessors to match Fluxor's real types.
import { runBacktest } from "../lib/backtest/engine";
import { defaultConfig } from "../lib/backtest/config";

type Bar = { ts: number; price_a: number; price_b: number };

// Deterministic PRNG so the oracle is reproducible.
function mulberry32(seed: number) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Replace every bar after k with a random walk that is wildly different from the original.
export function perturbFuture(bars: Bar[], k: number, seed = 1): Bar[] {
  const rnd = mulberry32(seed);
  const out = bars.map((b) => ({ ...b }));
  for (let i = k + 1; i < out.length; i++) {
    const shock = 1 + (rnd() - 0.5) * 0.2; // +-10% per bar
    out[i].price_a = out[i - 1].price_a * shock;
    out[i].price_b = out[i - 1].price_b * (1 + (rnd() - 0.5) * 0.2);
  }
  return out;
}

// TODO: confirm equity is aligned 1:1 with bars. If it is an array of {ts, equity}, map to numbers here.
// EquityPoint = { ts, naive, friction }. Compare both curves.
const equityAt = (r: any): number[][] => [r.equity.map((e: any) => e.naive), r.equity.map((e: any) => e.friction)];
// TODO: confirm trade field names. Only trades fully closed by cutoff are compared.
// If exit_time is a bar INDEX rather than a ts, the clean run below will print true; then compare against k instead of kTs.
const closedBy = (r: any, kTs: number) => r.trades.filter((t: any) => t.exit_time <= kTs);

const entriesBy = (r: any, kTs: number) =>
  r.trades
    .filter((t: any) => t.entry_time <= kTs)
    .map((t: any) => ({ entry_time: t.entry_time, direction: t.direction, entry_dev_bps: t.entry_dev_bps }));

export function metamorphicCheck(
  bars: Bar[], config: any, k: number, latency_ms?: number, seed = 1,
): { ok: boolean; reason?: string } {
  const base = runBacktest(bars, config, latency_ms);
  const pert = runBacktest(perturbFuture(bars, k, seed), config, latency_ms);

  const [bn, bf] = equityAt(base);
  const [pn, pf] = equityAt(pert);
  // Guard against a vacuous pass: curves must exist and hold real numbers.
  if (!bn.length || bn.slice(0, k + 1).some((v) => !Number.isFinite(v))) {
    return { ok: false, reason: "equity empty or non-numeric (wrong field?)" };
  }
  for (let i = 0; i <= k; i++) {
    if (Math.abs(bn[i] - pn[i]) > 1e-9 || Math.abs(bf[i] - pf[i]) > 1e-9) {
      return { ok: false, reason: `equity differs at bar ${i}` };
    }
  }
  const kTs = bars[k].ts;
  if (JSON.stringify(closedBy(base, kTs)) !== JSON.stringify(closedBy(pert, kTs))) {
    return { ok: false, reason: "closed trades before cutoff differ" };
  }
  // Entry decisions made at or before k must not depend on the future (catches 1-bar lookahead).
  if (JSON.stringify(entriesBy(base, kTs)) !== JSON.stringify(entriesBy(pert, kTs))) {
    return { ok: false, reason: "entry decisions at or before cutoff differ" };
  }
  return { ok: true };
}

// Run across several cutoffs and seeds; a leak is flagged if ANY check fails.
export function hasLeak(bars: Bar[], config: any, latency_ms?: number): boolean {
  const n = bars.length;
  // A lookahead only shows when the cutoff lands on a decision bar (an entry or exit).
  // So take cutoffs from the clean run's trades, plus a few evenly spaced ones.
  const idx = new Map<number, number>(bars.map((b, i) => [b.ts, i]));
  const base: any = runBacktest(bars, config, latency_ms);
  // Cutoffs must leave room for a forced exit: a position still open at the end of the data is never recorded as a
  // trade, so a perturbed run could "lose" an entry that is legitimately before the cutoff (false positive).
  // The hold bound is the larger of the configured max_hold_min and the longest hold actually observed, so an edit
  // that lengthens the hold limit does not reopen the gap.
  const hold = Math.max(Number(config?.strategy?.max_hold_min ?? 0), ...base.trades.map((t: any) => Number(t.hold_minutes) || 0));
  const kMax = n - 2 - hold;
  const ks = new Set<number>();
  for (let c = 1; c <= 20; c++) {
    const k = Math.floor((n * c) / 21);
    if (k <= kMax) ks.add(k);
  }
  for (const t of base.trades) {
    for (const ts of [t.entry_time, t.exit_time]) {
      const i = idx.get(ts);
      if (i !== undefined && i <= kMax) ks.add(i);
    }
  }
  let c = 0;
  for (const k of ks) {
    if (!metamorphicCheck(bars, config, k, latency_ms, 1 + (c++ % 3)).ok) return true;
  }
  return false;
}

// Sanity script: clean engine must report NO leak. Run: npx tsx leakbench/oracle.ts
if (require.main === module) {
  const n = 2000;
  const bars: Bar[] = Array.from({ length: n }, (_, i) => ({
    ts: i * 60_000,
    price_a: 100 + Math.sin(i / 30) * 2,
    price_b: 100 + Math.sin(i / 30) * 2 + Math.sin(i / 7) * 1.5 + Math.sin(i * 1.7) * 0.8,
  }));
  const config: any = defaultConfig();
  const r: any = runBacktest(bars, config);
  console.log("trades:", r.trades.length, "| first equity pt:", JSON.stringify(r.equity[0]), "| last:", JSON.stringify(r.equity[r.equity.length - 1]));
  console.log("first trade exit_time:", r.trades[0]?.exit_time, "| bars[10].ts:", bars[10].ts);
  console.log("check at 50%:", JSON.stringify(metamorphicCheck(bars, config, Math.floor(n * 0.5))));
  console.log("leak (expect false when clean, true when bug planted):", hasLeak(bars, config));
}