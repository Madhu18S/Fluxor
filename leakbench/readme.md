# LeakBench

A benchmark of 40 look-ahead mutants of Fluxor's `runBacktest` (TypeScript), plus a future-perturbation
non-interference oracle and the scripts behind the paper's three experiments (E1, E2, E4).
Every mutant passes a functional smoke suite; the oracle checks that changing bars after a cutoff
does not change anything observable at or before it.

Paper: [Kaggle writeup link]  |  Commit: [git rev-parse --short HEAD]  |  Node: [node -v]

## Files
| Path | What it is |
|---|---|
| `lib/backtest/engine.ts`, `config.ts` | The engine under test (clean version) |
| `leakbench/oracle.ts` | The non-interference oracle (`hasLeak`) |
| `leakbench/smoke_test.ts` | Functional smoke suite |
| `leakbench/generate.ts`, `check_one.ts` | Generate the 30 Family A mutants |
| `leakbench/exp_run.ts`, `exp_lib.ts`, `exp_child.ts` | Experiment runner (E3, E1, E2, E4) |
| `leakbench/tasks/*.json` | The 40 task definitions (30 Family A, 10 Family B) |
| `leakbench/results/e1, e2, e4 (.json, .md)` | Results reported in the paper |
| `leakbench/baseline.py` | Optional Gemma baseline harness (MLX). **Not used in the paper.** |

## Task format
Each JSON has `task_id`, `family`, `bug_type`, `variant`, `lookahead_bars`, `clean_line`, `mutated_line`,
`tests_pass`, `oracle_detects_leak`, `valid`. A mutation replaces `clean_line` with `mutated_line`
(first match inside `runBacktest`).

## Reproduce
Requires Node 18+.
```
npm install
git checkout lib/backtest/engine.ts
npx tsx leakbench/oracle.ts        # sanity check: last line should say false on the clean engine
TEST_CMD="npx tsx leakbench/smoke_test.ts" npx tsx leakbench/generate.ts   # Family A (30 tasks)
npx tsx leakbench/exp_run.ts all   # E3 (Family B), E1, E2, E4; takes a few minutes
cat leakbench/results/e1.md leakbench/results/e2.md leakbench/results/e4.md
```
The experiment scripts temporarily edit `lib/backtest/engine.ts` and restore it afterwards.
If a run is interrupted, run `git checkout lib/backtest/engine.ts`.

## Notes and limitations
- Synthetic data (2,000 one-minute bars), one engine, no automated repair-agent runs.
- The oracle was developed against a planted Family A bug in this engine, so detection rates are in-sample.
- The oracle assumes holding time is bounded (see the paper's end-of-data rule).
- "Functional tests" means `smoke_test.ts`, not a full unit-test suite.

## License
[Add a license, or state "all rights reserved".]
