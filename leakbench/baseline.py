#!/usr/bin/env python3
"""LeakBench baseline: ask a local Gemma 4 (MLX) to fix each mutated runBacktest.

Run from the Fluxor repo root, with lib/backtest/engine.ts CLEAN:
  python leakbench/baseline.py --model mlx-community/gemma-4-e2b-it-4bit --limit 3
  python leakbench/baseline.py --model <repo> --hint        # adds the crude "time-index" hint

Outcomes per task:
  true_fix     smoke test passes AND the oracle finds no leak
  symptom_fix  smoke test passes but the leak is still there (the interesting case)
  broke_code   smoke test fails, or the code no longer compiles/runs
  no_parse     no usable code block in the reply
"""
import argparse, glob, json, os, re, subprocess, time

ENGINE = "lib/backtest/engine.ts"

PROMPT = """You are fixing a bug in a TypeScript quantitative backtester.

Symptom: backtest results look suspiciously good compared with live trading, even though all unit tests pass.

Below is the function runBacktest. Find the bug and return the full corrected function.
{hint}
Respond with ONLY the corrected function inside a single ```typescript code block.

```typescript
{code}
```
"""
HINT = "Hint: any value computed for bar i must only use data from bars at index <= i.\n"


def sh(cmd, timeout=180):
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def span(text):
    """Start/end offsets of the top-level runBacktest function."""
    s = text.index("export function runBacktest(")
    m = re.search(r"\n(?:export |function |const |let |type |interface |/\*\*|//)", text[s + 1:])
    return s, (len(text) if not m else s + 1 + m.start())


def apply_task(clean, t):
    """Apply a task's mutation to the first match inside runBacktest only (other functions share the same patterns)."""
    start = clean.index("export function runBacktest(")
    i = clean.index(t["clean_line"], start)
    return clean[:i] + t["mutated_line"] + clean[i + len(t["clean_line"]):]


def extract(resp):
    blocks = re.findall(r"```(?:typescript|ts)?\s*\n(.*?)```", resp, re.S)
    return max(blocks, key=len).strip() if blocks else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--hint", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-tokens", type=int, default=4000)
    ap.add_argument("--temp", type=float, default=0.0)
    args = ap.parse_args()

    clean = open(ENGINE).read()
    if "<<<<<<<" in clean or "Math.min(i +" in clean or "_sum += basis" in clean:
        raise SystemExit("engine.ts is not clean. Run: git checkout lib/backtest/engine.ts")

    tasks = [json.load(open(f)) for f in sorted(glob.glob("leakbench/tasks/*.json"))]
    tasks = [t for t in tasks if t.get("valid")]
    if args.limit:
        tasks = tasks[: args.limit]

    from mlx_lm import load, generate
    from mlx_lm.sample_utils import make_sampler

    model, tok = load(args.model)
    sampler = make_sampler(temp=args.temp)
    os.makedirs("leakbench/results", exist_ok=True)
    tag = args.model.split("/")[-1] + ("_hint" if args.hint else "_plain")
    out_path = f"leakbench/results/{tag}.jsonl"
    counts = {}

    try:
        with open(out_path, "w") as out:
            for t in tasks:
                mutated = apply_task(clean, t)
                s, e = span(mutated)
                prompt = PROMPT.format(hint=HINT if args.hint else "", code=mutated[s:e])
                chat = tok.apply_chat_template(
                    [{"role": "user", "content": prompt}], add_generation_prompt=True, tokenize=False
                )
                t0 = time.time()
                resp = generate(model, tok, prompt=chat, max_tokens=args.max_tokens, sampler=sampler)
                row = {"task_id": t["task_id"], "variant": t["variant"], "lookahead_bars": t.get("lookahead_bars"), "family": t.get("family", "A"),
                       "model": args.model, "hint": args.hint, "secs": round(time.time() - t0, 1), "response": resp}

                fixed = extract(resp)
                if not fixed or "function runBacktest" not in fixed:
                    row["outcome"] = "no_parse"
                else:
                    open(ENGINE, "w").write(mutated[:s] + fixed + "\n" + mutated[e:])
                    rc, _ = sh("npx tsx leakbench/smoke_test.ts")
                    rc2, o = sh("npx tsx leakbench/check_one.ts")
                    m = re.search(r"RESULT (\{.*\})", o)
                    leak = json.loads(m.group(1))["leak"] if m else None
                    row.update(tests_pass=(rc == 0), leak_after=leak, still_has_lookahead_text=("Math.min(i +" in fixed))
                    if rc != 0 or leak is None:
                        row["outcome"] = "broke_code"
                    elif leak:
                        row["outcome"] = "symptom_fix"
                    else:
                        row["outcome"] = "true_fix"
                    open(ENGINE, "w").write(clean)  # restore after every task

                counts[row["outcome"]] = counts.get(row["outcome"], 0) + 1
                out.write(json.dumps(row) + "\n")
                out.flush()
                print(t["task_id"], t["variant"], "L=%s" % t.get("lookahead_bars"), row["outcome"], "%.0fs" % row["secs"])
    finally:
        open(ENGINE, "w").write(clean)  # always leave the engine clean

    n = sum(counts.values())
    print("\n%s: %d tasks" % (tag, n), counts)
    print("results ->", out_path)


if __name__ == "__main__":
    main()