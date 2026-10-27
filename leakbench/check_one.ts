// Runs the oracle once against whatever engine.ts is currently on disk. Called by generate.ts in a fresh process.
import { hasLeak } from "./oracle";
import { defaultConfig } from "../lib/backtest/config";

const n = 2000;
const bars = Array.from({ length: n }, (_, i) => ({
  ts: i * 60_000,
  price_a: 100 + Math.sin(i / 30) * 2,
  price_b: 100 + Math.sin(i / 30) * 2 + Math.sin(i / 7) * 1.5 + Math.sin(i * 1.7) * 0.8,
}));
console.log("RESULT " + JSON.stringify({ leak: hasLeak(bars, defaultConfig() as any) }));