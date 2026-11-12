// Shared helpers for the LeakBench experiments. Loaded only by exp_child.ts (a fresh process per engine variant).
import { runBacktest } from "../lib/backtest/engine";
import { defaultConfig } from "../lib/backtest/config";
import { perturbFuture } from "./oracle";
import { createHash } from "crypto";

export type Bar = { ts: number; price_a: number; price_b: number };

function rng(seed: number) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Four synthetic data regimes. "sine" is the one used in oracle.ts and generate.ts.
export function makeBars(kind: string, n = 2000): Bar[] {
  const r = rng(1000 + kind.length);
  const g = () => (r() + r() + r() + r() - 2) * 1.732; // roughly N(0,1)
  const bars: Bar[] = [];
  let pa = 100;
  let s = 0;
  for (let i = 0; i < n; i++) {
    let a: number, b: number;
    if (kind === "sine") {
      a = 100 + Math.sin(i / 30) * 2;
      b = a + Math.sin(i / 7) * 1.5 + Math.sin(i * 1.7) * 0.8;
    } else if (kind === "noisy") {
      a = 100 + Math.sin(i / 30) * 2;
      b = a + Math.sin(i / 7) * 1.5 + g() * 0.6;
    } else if (kind === "trend") {
      a = 100 + i * 0.003 + Math.sin(i / 45) * 1.5;
      b = a + Math.sin(i / 9) * 1.2 + g() * 0.3;
    } else {
      // "rw": random-walk level with an AR(1) spread in bps
      pa *= 1 + g() * 0.0005;
      s = 0.9 * s + g() * 15;
      a = pa;
      b = pa * (1 + s / 1e4);
    }
    bars.push({ ts: i * 60_000, price_a: a, price_b: b });
  }
  return bars;
}

// Default config with strategy fields overridden (over) or scaled (mult).
export function cfgWith(over: Record<string, number> = {}, mult: Record<string, number> = {}): any {
  const d: any = defaultConfig();
  const strategy: any = { ...d.strategy, ...over };
  for (const [k, m] of Object.entries(mult)) strategy[k] = d.strategy[k] * m;
  return defaultConfig({ strategy } as any);
}

export type Obs = { equity: boolean; closed: boolean; entries: boolean };
export type Cut = { mode: "even"; count: number } | { mode: "tradelog"; extraEven: number };

const EPS = 1e-9;

// true = the future perturbation changed something observable at or before cutoff k.
function violates(base: any, pert: any, bars: Bar[], k: number, obs: Obs): boolean {
  const kTs = bars[k].ts;
  if (obs.equity) {
    for (let i = 0; i <= k; i++) {
      const a = base.equity[i];
      const b = pert.equity[i];
      if (![a.naive, a.friction, b.naive, b.friction].every(Number.isFinite)) return true;
      if (Math.abs(a.naive - b.naive) > EPS || Math.abs(a.friction - b.friction) > EPS) return true;
    }
  }
  if (obs.closed) {
    const f = (r: any) => JSON.stringify(r.trades.filter((t: any) => t.exit_time <= kTs));
    if (f(base) !== f(pert)) return true;
  }
  if (obs.entries) {
    const f = (r: any) =>
      JSON.stringify(
        r.trades.filter((t: any) => t.entry_time <= kTs).map((t: any) => [t.entry_time, t.direction, t.entry_dev_bps]),
      );
    if (f(base) !== f(pert)) return true;
  }
  return false;
}

// Same cutoff construction as oracle.ts (insertion order matters for seed assignment).
function cutoffs(bars: Bar[], base: any, cut: Cut, config: any): number[] {
  const n = bars.length;
  // Leave room for a forced exit (same rule as oracle.ts).
  const hold = Math.max(Number(config?.strategy?.max_hold_min ?? 0), ...base.trades.map((t: any) => Number(t.hold_minutes) || 0));
  const kMax = n - 2 - hold;
  const ks = new Set<number>();
  const even = cut.mode === "even" ? cut.count : cut.extraEven;
  for (let c = 1; c <= even; c++) {
    const k = Math.floor((n * c) / (even + 1));
    if (k <= kMax) ks.add(k);
  }
  if (cut.mode === "tradelog") {
    const idx = new Map<number, number>(bars.map((b, i) => [b.ts, i]));
    for (const t of base.trades) {
      for (const ts of [t.entry_time, t.exit_time]) {
        const i = idx.get(ts);
        if (i !== undefined && i <= kMax) ks.add(i);
      }
    }
  }
  return [...ks];
}

export function detects(bars: Bar[], config: any, obs: Obs, cut: Cut, latency_ms?: number): boolean {
  const base: any = runBacktest(bars, config, latency_ms);
  let c = 0;
  for (const k of cutoffs(bars, base, cut, config)) {
    const pert: any = runBacktest(perturbFuture(bars, k, 1 + (c++ % 3)), config, latency_ms);
    if (violates(base, pert, bars, k, obs)) return true;
  }
  return false;
}

const ALL: Obs = { equity: true, closed: true, entries: true };
export const VARIANTS: { id: string; obs: Obs; cut: Cut }[] = [
  { id: "V0_equity_even20", obs: { equity: true, closed: false, entries: false }, cut: { mode: "even", count: 20 } },
  { id: "V1_equity+closed_even20", obs: { equity: true, closed: true, entries: false }, cut: { mode: "even", count: 20 } },
  { id: "V2_all_even20", obs: ALL, cut: { mode: "even", count: 20 } },
  { id: "V2_all_even60", obs: ALL, cut: { mode: "even", count: 60 } },
  { id: "V2_all_even200", obs: ALL, cut: { mode: "even", count: 200 } },
  { id: "V3_all_tradelog", obs: ALL, cut: { mode: "tradelog", extraEven: 20 } }, // = final oracle in oracle.ts
];

export const tradesHash = (r: any): string => createHash("sha1").update(JSON.stringify(r.trades)).digest("hex").slice(0, 12);