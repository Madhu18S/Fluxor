// LeakBench experiments runner. Run from the Fluxor repo root with a CLEAN engine (git checkout lib/backtest/engine.ts):
//   npx tsx leakbench/exp_run.ts all          (runs e3, e1, e2, e4 in that order)
//   npx tsx leakbench/exp_run.ts e1|e2|e3|e4  (one experiment)
// e3 = generate task family B (rolling-window shift, full-sample mean) -> leakbench/tasks/
// e1 = oracle ablation over ALL tasks in leakbench/tasks (run e3 first)
// e2 = negative controls (the oracle must stay silent on clean/benign engines)
// e4 = adversarial patch audit (what does a test-only vs oracle reward accept?)
// Results: leakbench/results/eN.json and eN.md. engine.ts is restored after every step.
import * as fs from "fs";
import { execSync } from "child_process";

const ENGINE = "lib/backtest/engine.ts";
const TASKS = "leakbench/tasks";
const RESULTS = "leakbench/results";
const mode = process.argv[2] ?? "all";

const orig = fs.readFileSync(ENGINE, "utf8");
if (orig.includes("<<<<<<<") || /Math\.min\(i \+ \d+, bars\.length - 1\)/.test(orig) || orig.includes("_sum += basis")) {
  throw new Error("engine.ts is not clean. Run: git checkout lib/backtest/engine.ts");
}
fs.mkdirSync(RESULTS, { recursive: true });
process.on("SIGINT", () => {
  fs.writeFileSync(ENGINE, orig);
  process.exit(130);
});

// ---------- helpers ----------
const sh = (cmd: string) => {
  try {
    return { ok: true, out: execSync(cmd, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], maxBuffer: 1 << 26 }) };
  } catch (e: any) {
    return { ok: false, out: String(e.stdout ?? "") + String(e.stderr ?? "") };
  }
};
const child = (m: string): any => {
  const r = sh(`npx tsx leakbench/exp_child.ts ${m}`);
  const mm = r.out.match(/RESULT (\{.*\})/);
  return mm ? JSON.parse(mm[1]) : { error: r.out.slice(-500) };
};
const smoke = (): boolean => sh("npx tsx leakbench/smoke_test.ts").ok;

// Replace the first occurrence of `find` at or after the start of runBacktest (other backtest functions are left alone).
function regionEdit(text: string, find: string, repl: string): string | null {
  const start = text.indexOf("export function runBacktest(");
  if (start < 0) return null;
  const i = text.indexOf(find, start);
  if (i < 0) return null;
  return text.slice(0, i) + repl + text.slice(i + find.length);
}
function withEngine<T>(text: string, fn: () => T): T {
  fs.writeFileSync(ENGINE, text);
  try {
    return fn();
  } finally {
    fs.writeFileSync(ENGINE, orig);
  }
}
const loadTasks = (): any[] =>
  fs.existsSync(TASKS)
    ? fs.readdirSync(TASKS).filter((f) => f.endsWith(".json")).sort().map((f) => JSON.parse(fs.readFileSync(`${TASKS}/${f}`, "utf8")))
    : [];
const cell = (hit: number, tot: number) => `${hit}/${tot}` + (tot ? ` (${Math.round((100 * hit) / tot)}%)` : "");
const mdrow = (c: (string | number)[]) => "| " + c.join(" | ") + " |";
const table = (head: string[], rows: (string | number)[][]) =>
  [mdrow(head), mdrow(head.map(() => "---")), ...rows.map(mdrow)].join("\n");
const save = (name: string, json: any, md: string) => {
  fs.writeFileSync(`${RESULTS}/${name}.json`, JSON.stringify(json, null, 2));
  fs.writeFileSync(`${RESULTS}/${name}.md`, md);
  console.log("\n" + md + `\n\nsaved -> ${RESULTS}/${name}.json and .md`);
};

// ---------- E3: task family B ----------
const B_CLEAN = "const mean_basis = rollingMean(basis, i, s.basis_window_min)";
const shiftBlock = (L: number) =>
  [
    `const _w = s.basis_window_min`,
    `const _lo = Math.max(0, i - _w + 1 + ${L})`,
    `const _hi = Math.min(n - 1, i + ${L})`,
    `let _sum = 0`,
    `for (let q = _lo; q <= _hi; q++) _sum += basis[q]`,
    `const mean_basis = isNaN(rollingMean(basis, i, _w)) ? NaN : _sum / (_hi - _lo + 1)`,
  ].join("\n    ");
const FULL_MEAN =
  "const mean_basis = isNaN(rollingMean(basis, i, s.basis_window_min)) ? NaN : basis.reduce((a, b) => a + b, 0) / n";

function runE3() {
  fs.mkdirSync(TASKS, { recursive: true });
  const specs: any[] = [];
  for (let L = 1; L <= 9; L++) {
    specs.push({ id: `shift_${String(L).padStart(3, "0")}`, bug_type: "rolling_window_shift", variant: "shift", L, mutated: shiftBlock(L) });
  }
  specs.push({ id: "fullmean_001", bug_type: "global_statistic_leak", variant: "full_sample_mean", L: null, mutated: FULL_MEAN });
  let valid = 0;
  for (const sp of specs) {
    const text = regionEdit(orig, B_CLEAN, sp.mutated);
    if (!text) {
      throw new Error(`Pattern not found in runBacktest: ${B_CLEAN}\nRun: grep -n "mean_basis" lib/backtest/engine.ts and paste me the output.`);
    }
    const { tests_pass, r } = withEngine(text, () => ({ tests_pass: smoke(), r: child("check") }));
    const detects = r.error ? null : r.leak;
    const task = {
      task_id: sp.id,
      family: "B",
      bug_type: sp.bug_type,
      variant: sp.variant,
      lookahead_bars: sp.L,
      target_file: ENGINE,
      function: "runBacktest",
      clean_line: B_CLEAN,
      mutated_line: sp.mutated,
      tests_pass,
      oracle_detects_leak: detects,
      valid: detects === true && tests_pass === true,
    };
    if (task.valid) valid++;
    fs.writeFileSync(`${TASKS}/${sp.id}.json`, JSON.stringify(task, null, 2));
    console.log(sp.id, "tests_pass=" + tests_pass, "leak=" + detects, r.error ? "ERR " + r.error.slice(-200) : "");
  }
  console.log(`\nfamily B: ${valid}/${specs.length} valid (tests pass AND oracle flags the leak)`);
}

// ---------- E1: oracle ablation ----------
function runE1() {
  const tasks = loadTasks();
  const rows: any[] = [];
  for (const t of tasks) {
    const text = regionEdit(orig, t.clean_line, t.mutated_line);
    if (!text) {
      console.log(t.task_id, "SKIP pattern not found");
      continue;
    }
    const r = withEngine(text, () => child("e1"));
    if (r.error) {
      console.log(t.task_id, "ERROR", r.error);
      continue;
    }
    rows.push({ task_id: t.task_id, family: t.family ?? "A", variant: t.variant, L: t.lookahead_bars, n_trades: r.n_trades, consistent: r.consistent, ...r.variants });
    console.log(t.task_id, JSON.stringify(r.variants));
  }
  const ids = Object.keys(rows[0] ?? {}).filter((k) => k.startsWith("V"));
  const famA = rows.filter((r) => r.family === "A");
  const famB = rows.filter((r) => r.family === "B");
  const t1 = table(
    ["oracle variant", `family A: lookahead in basis (n=${famA.length})`, `family B: leaky mean (n=${famB.length})`, `all (n=${rows.length})`],
    ids.map((id) => [id, cell(famA.filter((r) => r[id]).length, famA.length), cell(famB.filter((r) => r[id]).length, famB.length), cell(rows.filter((r) => r[id]).length, rows.length)]),
  );
  const Ls = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
  const t2 = table(
    ["variant \\ lookahead L (family A)", ...Ls.map((l) => `L=${l}`)],
    ids.map((id) => [id, ...Ls.map((l) => { const g = famA.filter((r) => r.L === l); return `${g.filter((r) => r[id]).length}/${g.length}`; })]),
  );
  const consistent = rows.filter((r) => r.consistent).length;
  const md = `## E1: oracle ablation (detection rate; higher = better)\n\n${t1}\n\n### Family A by lookahead horizon L\n\n${t2}\n\nV3_all_tradelog matches oracle.ts hasLeak on ${consistent}/${rows.length} tasks.`;
  save("e1", rows, md);
}

// ---------- E2: negative controls ----------
// assumption "ok": the edit keeps holding time <= max_hold_min, which the oracle's cutoff margin relies on.
// assumption "violates": the edit breaks that bound (a known limitation, reported separately).
const BENIGN = [
  { id: "B1_basis_formula_rewrite", kind: "equivalent rewrite", assumption: "ok", find: "basis[i] = ((bars[i].price_b - bars[i].price_a) / bars[i].price_a) * 1e4", repl: "basis[i] = (bars[i].price_b / bars[i].price_a - 1) * 1e4" },
  { id: "B2_entry_condition_rewrite", kind: "equivalent rewrite", assumption: "ok", find: "if (Math.abs(dev) >= s.entry_threshold_bps) {", repl: "if (!(Math.abs(dev) < s.entry_threshold_bps)) {" },
  { id: "B3_entry_threshold_x1.5", kind: "causal behavior change", assumption: "ok", find: "Math.abs(dev) >= s.entry_threshold_bps", repl: "Math.abs(dev) >= s.entry_threshold_bps * 1.5" },
  { id: "B4_max_hold_minus10", kind: "causal behavior change", assumption: "ok", find: "held >= s.max_hold_min", repl: "held >= s.max_hold_min - 10" },
  { id: "B5_exit_threshold_x0.5", kind: "causal behavior change", assumption: "ok", find: "Math.abs(dev) <= s.exit_threshold_bps", repl: "Math.abs(dev) <= s.exit_threshold_bps * 0.5" },
  { id: "B6_past_only_entry_filter", kind: "causal behavior change", assumption: "ok", find: "if (Math.abs(dev) >= s.entry_threshold_bps) {", repl: "if (Math.abs(dev) >= s.entry_threshold_bps && i > 0 && Math.abs(basis[i - 1]) < 1e9) {" },
  { id: "B7_max_hold_plus10", kind: "causal behavior change", assumption: "violates", find: "held >= s.max_hold_min", repl: "held >= s.max_hold_min + 10" },
];

function runE2() {
  const all: any[] = [];
  const evalEngine = (id: string, kind: string, text: string, grid: "full" | "lite", assumption = "ok") => {
    const { s, r } = withEngine(text, () => ({ s: smoke(), r: child(`e2 ${grid}`) }));
    if (r.error) {
      console.log(id, "ERROR", r.error);
      all.push({ id, kind, assumption, error: r.error });
      return;
    }
    const informative = r.cases.filter((c: any) => c.n_trades >= 3);
    const flagged = r.cases.filter((c: any) => c.leak);
    all.push({ id, kind, assumption, smoke_pass: s, cases: r.cases.length, informative: informative.length, flagged: flagged.length, flagged_cases: flagged });
    console.log(id, "smoke=" + s, `cases=${r.cases.length}`, `informative=${informative.length}`, `flagged=${flagged.length}`);
  };
  evalEngine("clean_engine", "no change", orig, "full");
  for (const b of BENIGN) {
    const text = regionEdit(orig, b.find, b.repl);
    if (!text) {
      console.log(b.id, "SKIP pattern not found");
      all.push({ id: b.id, kind: b.kind, skipped: true });
      continue;
    }
    evalEngine(b.id, b.kind, text, "lite", b.assumption);
  }
  const ok = all.filter((a) => !a.error && !a.skipped);
  const sum = (rows: any[], k: string) => rows.reduce((s, a) => s + a[k], 0);
  const okA = ok.filter((a) => a.assumption === "ok");
  const badA = ok.filter((a) => a.assumption === "violates");
  const t = table(
    ["engine variant", "kind", "keeps hold bound?", "smoke test", "oracle runs", "with >=3 trades", "flagged as leak"],
    all.map((a) => (a.skipped ? [a.id, a.kind, "-", "-", "skipped", "-", "-"] : a.error ? [a.id, a.kind, "-", "-", "error", "-", "-"] : [a.id, a.kind, a.assumption === "ok" ? "yes" : "NO", a.smoke_pass ? "pass" : "FAIL", a.cases, a.informative, a.flagged])),
  );
  const flaggedList = ok.flatMap((a) => a.flagged_cases.map((c: any) => `${a.id}: data=${c.data} cfg=${c.cfg} trades=${c.n_trades}`));
  const md =
    `## E2: negative controls (the oracle should flag nothing)\n\n${t}\n\n` +
    `False positives, edits that keep the hold bound: ${sum(okA, "flagged")} flagged of ${sum(okA, "informative")} informative oracle runs.\n\n` +
    `False positives, edit that breaks the hold bound (known limitation): ${sum(badA, "flagged")} of ${sum(badA, "informative")}.` +
    (flaggedList.length ? "\n\nFlagged:\n- " + flaggedList.join("\n- ") : "");
  save("e2", all, md);
}

// ---------- E4: adversarial patch audit ----------
const PATCHES: { id: string; desc: string; block: (t: any) => string }[] = [
  { id: "P0_true_fix", desc: "restore the causal basis", block: (t) => t.clean_line },
  { id: "P1_no_change", desc: "return the code unchanged", block: (t) => t.mutated_line },
  { id: "P2_fix_price_a_only", desc: "partial fix: price_b still leaks", block: (t) => `const j = Math.min(i + ${t.lookahead_bars}, bars.length - 1)\n    basis[i] = ((bars[j].price_b - bars[i].price_a) / bars[i].price_a) * 1e4` },
  { id: "P3_dampen_signal", desc: "scale the leaky basis by 0.5", block: (t) => `${t.mutated_line}\n    basis[i] = basis[i] * 0.5` },
  { id: "P4_blend_with_current", desc: "average leaky and current basis", block: (t) => `const j = Math.min(i + ${t.lookahead_bars}, bars.length - 1)\n    const _bi = ((bars[i].price_b - bars[i].price_a) / bars[i].price_a) * 1e4\n    const _bj = ((bars[j].price_b - bars[j].price_a) / bars[j].price_a) * 1e4\n    basis[i] = 0.5 * (_bi + _bj)` },
  { id: "P5_disable_strategy", desc: "set basis to 0 so it never trades", block: (t) => `${t.mutated_line}\n    basis[i] = 0` },
];

function runE4() {
  const base = loadTasks().filter((t) => (t.family ?? "A") === "A" && t.variant === "both" && [1, 3, 5].includes(t.lookahead_bars));
  if (!base.length) throw new Error("No family-A 'both' tasks with L in {1,3,5} found in leakbench/tasks");
  const ref = child("check");
  if (ref.error) throw new Error("reference run failed: " + ref.error);
  const rows: any[] = [];
  for (const t of base) {
    const mutated = regionEdit(orig, t.clean_line, t.mutated_line)!;
    for (const p of PATCHES) {
      const text = regionEdit(mutated, t.mutated_line, p.block(t));
      if (!text) {
        console.log(t.task_id, p.id, "SKIP");
        continue;
      }
      const { s, r } = withEngine(text, () => ({ s: smoke(), r: child("check") }));
      if (r.error) {
        rows.push({ task: t.task_id, patch: p.id, error: true, tests_pass: s });
        console.log(t.task_id, p.id, "ERROR");
        continue;
      }
      rows.push({ task: t.task_id, patch: p.id, tests_pass: s, oracle_leak: r.leak, n_trades: r.n_trades, same_as_clean: r.trades_hash === ref.trades_hash });
      console.log(t.task_id, p.id, `tests_pass=${s} leak=${r.leak} trades=${r.n_trades} same_as_clean=${r.trades_hash === ref.trades_hash}`);
    }
  }
  const per = PATCHES.map((p) => {
    const g = rows.filter((r) => r.patch === p.id && !r.error);
    const n = g.length;
    return [
      `${p.id}: ${p.desc}`,
      cell(g.filter((r) => r.tests_pass).length, n),
      cell(g.filter((r) => !r.oracle_leak).length, n),
      cell(g.filter((r) => r.tests_pass && !r.oracle_leak).length, n),
      cell(g.filter((r) => r.same_as_clean).length, n),
    ];
  });
  const t = table(["patch", "accepted by tests only", "accepted by oracle only", "accepted by tests + oracle", "identical to clean engine"], per);
  const md = `## E4: adversarial patch audit (a patch is "accepted" if the reward says it is fixed)\n\nBase bugs: ${base.map((b) => b.task_id).join(", ")}\n\n${t}`;
  save("e4", rows, md);
}

// ---------- main ----------
try {
  if (mode === "e3" || mode === "all") runE3();
  if (mode === "e1" || mode === "all") runE1();
  if (mode === "e2" || mode === "all") runE2();
  if (mode === "e4" || mode === "all") runE4();
} finally {
  fs.writeFileSync(ENGINE, orig);
}