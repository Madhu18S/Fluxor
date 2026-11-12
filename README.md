# Fluxor

Fluxor is a friction-aware backtesting tool for crypto arbitrage. It checks whether cross-venue price gaps still make money after fees, slippage, gas and execution latency, using real exchange and on-chain data.

> **Status:** work in progress (~75% built).

## Features
- **Backtester** (`lib/backtest/`): cross-venue basis mean-reversion strategy. It computes the basis between two venues, enters when the deviation from its rolling mean exceeds a threshold, and exits on reversion or a max hold. It models fees, slippage and latency, and outputs trades and equity curves.
- **Three arbitrage modules**, each with its own API route and dashboard tab:
  - **CEX-CEX**: Binance.US vs Coinbase, BTC/USD, 1-minute bars (`/api/backtest`).
  - **Triangular**: single-venue on Kraken (BTC/USD, ETH/USD, ETH/BTC), 6-leg round trip (`/api/backtest/triangular`).
  - **CEX-DEX**: Kraken ETH/USD vs a Uniswap v3 pool via The Graph, with per-swap gas (`/api/backtest/cexdex`).
- **Friction layer** (`lib/backtest/friction.ts`): exchange fee tiers, slippage, and latency. Triangular and CEX-DEX sample latency per trade from a Gamma distribution; CEX-CEX uses a deterministic decay.
- **Metrics**: annualized Sharpe, win rate, max drawdown, gross vs net spread (phantom alpha), and a latency-sensitivity sweep.
- **Dashboard** (`components/`): Next.js UI with one tab per module.

## Quick start
```
git clone https://github.com/Madhu18S/Fluxor.git
cd Fluxor
npm install
npm run dev
```
Requires Node 20.9+ (Next.js 16).

The CEX-DEX module needs a free API key from [The Graph](https://thegraph.com/studio). Put it in `.env.local`:
```
THEGRAPH_API_KEY=your_key_here
```
CEX-CEX and Triangular use public REST endpoints and need no keys.

## Project structure
| Path | Contents |
|---|---|
| `lib/backtest/engine.ts` | `runBacktest(bars, config, latency_ms?)`, `runTriangularBacktest`, `runCexDexBacktest` |
| `lib/backtest/config.ts` | `BacktestConfig` and `defaultConfig()`, fee tiers, Gamma latency settings |
| `lib/backtest/friction.ts` | Fees, slippage, latency decay, Gamma sampler |
| `lib/backtest/data.ts` | Binance.US, Coinbase, Kraken and Uniswap v3 (The Graph) loaders |
| `lib/backtest/metrics.ts` | Sharpe, drawdown, win rate, latency sweep |
| `app/api/backtest/` | API routes for the three modules |
| `components/` | Dashboard UI (`components/modules/` has one component per module) |
| `leakbench/` | LeakBench: look-ahead-bug benchmark and oracle for this engine (see [leakbench/README.md](leakbench/README.md)) |

## LeakBench
`leakbench/` holds 40 look-ahead mutants of `runBacktest`, a future-perturbation non-interference oracle, and the experiment scripts. It was built for the Kaggle Gemma 4 Developer Agent Paper Track. See [leakbench/README.md](leakbench/README.md).

## Notes and limitations
- Fee tiers are approximate and change over time. Check each exchange's current schedule before citing any number.
- Kraken's public OHLC endpoint caps at 720 candles per call and doesn't page backward reliably at 1-minute resolution, so the Triangular and CEX-DEX modules use coarser bars and flag a truncated window.
- Data comes from REST/GraphQL polling of historical bars, not live order-book streams.
- At retail fee tiers the strategies mostly lose money after friction. That is the finding, not a bug.

## Roadmap
- Live WebSocket L2 order-book ingestion (Binance.US, Coinbase, Kraken) and a Uniswap v3 swap-event listener.
- Q-learning smart order router that picks maker/taker/split per trade, trained against the friction model.
- Maker-order economics and volume-tier fee selection in the UI.
- Unit tests for the engine, friction and metrics.

## License
All rights reserved.
