// Functional smoke test for runBacktest. Exits non-zero on failure.
// It checks ordinary correctness (sane shapes, finite numbers, non-negative costs), NOT temporal leakage.
import { runBacktest } from "../lib/backtest/engine";
import { defaultConfig } from "../lib/backtest/config";

const n = 2000;
const bars = Array.from({ length: n }, (_, i) => ({
  ts: i * 60_000,
  price_a: 100 + Math.sin(i / 30) * 2,
  price_b: 100 + Math.sin(i / 30) * 2 + Math.sin(i / 7) * 1.5 + Math.sin(i * 1.7) * 0.8,
}));
const config: any = defaultConfig();
const r: any = runBacktest(bars, config);

const fail = (msg: string) => {
  console.error("SMOKE FAIL:", msg);
  process.exit(1);
};

if (r.n_bars !== n) fail("n_bars mismatch");
if (r.equity.length !== n) fail("equity length != bars");
if (!r.trades.length) fail("no trades produced");
if (Math.abs(r.equity[0].friction - config.starting_capital) > 1e-6) fail("equity does not start at starting_capital");
for (const e of r.equity) {
  if (!Number.isFinite(e.naive) || !Number.isFinite(e.friction)) fail("non-finite equity");
}
for (let i = 1; i < r.equity.length; i++) {
  if (r.equity[i].ts <= r.equity[i - 1].ts) fail("equity timestamps not increasing");
}
for (const t of r.trades) {
  if (t.exit_time < t.entry_time) fail("trade exits before entry");
  if (t.hold_minutes < 0) fail("negative hold");
  if (t.fee_cost_bps < 0 || t.slippage_cost_bps < 0) fail("negative cost");
  if (!Number.isFinite(t.net_pnl) || !Number.isFinite(t.gross_pnl)) fail("non-finite pnl");
  if (t.direction !== "long_A_short_B" && t.direction !== "short_A_long_B") fail("bad direction");
}
console.log("SMOKE OK:", r.trades.length, "trades");