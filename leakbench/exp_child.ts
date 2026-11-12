// Runs one measurement against whatever lib/backtest/engine.ts is currently on disk, then prints a RESULT line.
// Called by exp_run.ts in a fresh process per engine variant:  npx tsx leakbench/exp_child.ts <check|e1|e2> [full|lite]
import { runBacktest } from "../lib/backtest/engine";
import { hasLeak } from "./oracle";
import { makeBars, cfgWith, detects, VARIANTS, tradesHash } from "./exp_lib";

const mode = process.argv[2];
const out = (o: any) => console.log("RESULT " + JSON.stringify(o));

if (mode === "check") {
  const bars = makeBars("sine");
  const cfg = cfgWith();
  const r: any = runBacktest(bars, cfg);
  out({
    leak: hasLeak(bars, cfg),
    n_trades: r.trades.length,
    final_friction: r.equity[r.equity.length - 1].friction,
    trades_hash: tradesHash(r),
  });
} else if (mode === "e1") {
  const bars = makeBars("sine");
  const cfg = cfgWith();
  const r: any = runBacktest(bars, cfg);
  const variants: Record<string, boolean> = {};
  for (const v of VARIANTS) variants[v.id] = detects(bars, cfg, v.obs, v.cut);
  out({ n_trades: r.trades.length, variants, consistent: variants["V3_all_tradelog"] === hasLeak(bars, cfg) });
} else if (mode === "e2") {
  const full = process.argv[3] === "full";
  const DATA = ["sine", "rw", "noisy", "trend"];
  const CFGS: { name: string; cfg: any; lat?: number }[] = [
    { name: "default", cfg: cfgWith() },
    { name: "entry_x1.5", cfg: cfgWith({}, { entry_threshold_bps: 1.5 }) },
  ];
  if (full) {
    CFGS.push(
      { name: "win30", cfg: cfgWith({ basis_window_min: 30 }) },
      { name: "win120", cfg: cfgWith({ basis_window_min: 120 }) },
      { name: "entry_x0.7", cfg: cfgWith({}, { entry_threshold_bps: 0.7 }) },
      { name: "latency100", cfg: cfgWith(), lat: 100 },
    );
  }
  const cases: any[] = [];
  for (const d of DATA) {
    const bars = makeBars(d);
    for (const c of CFGS) {
      const r: any = runBacktest(bars, c.cfg, c.lat);
      cases.push({ data: d, cfg: c.name, n_trades: r.trades.length, leak: hasLeak(bars, c.cfg, c.lat) });
    }
  }
  out({ cases });
} else {
  throw new Error("unknown mode " + mode);
}