// Generates LeakBench lookahead tasks from Fluxor's runBacktest.
// Run from the Fluxor repo root, with engine.ts CLEAN (git checkout lib/backtest/engine.ts):
//   TEST_CMD="npm test" npx tsx leakbench/generate.ts      (omit TEST_CMD if you have no unit tests)
import * as fs from "fs";
import { execSync } from "child_process";

const ENGINE = "lib/backtest/engine.ts";
const CLEAN = "basis[i] = ((bars[i].price_b - bars[i].price_a) / bars[i].price_a) * 1e4";
const TEST_CMD = process.env.TEST_CMD;

const orig = fs.readFileSync(ENGINE, "utf8");
if (orig.split(CLEAN).length !== 2) {
  throw new Error("Expected exactly one clean basis line. Run: git checkout lib/backtest/engine.ts");
}
fs.mkdirSync("leakbench/tasks", { recursive: true });

const sh = (cmd: string) => {
  try {
    return { ok: true, out: execSync(cmd, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }) };
  } catch (e: any) {
    return { ok: false, out: String(e.stdout ?? "") + String(e.stderr ?? "") };
  }
};

let id = 0;
let valid = 0;
try {
  for (const variant of ["both", "b_only", "a_only"]) {
    for (let L = 1; L <= 10; L++) {
      const pa = variant === "b_only" ? "i" : "j"; // price_a from future bar?
      const pb = variant === "a_only" ? "i" : "j"; // price_b from future bar?
      const mutated =
        `const j = Math.min(i + ${L}, bars.length - 1)\n` +
        `    basis[i] = ((bars[${pb}].price_b - bars[${pa}].price_a) / bars[${pa}].price_a) * 1e4`;

      fs.writeFileSync(ENGINE, orig.replace(CLEAN, () => mutated));
      const tests_pass = TEST_CMD ? sh(TEST_CMD).ok : null; // null = no tests configured (unknown)
      const r = sh("npx tsx leakbench/check_one.ts");
      const m = r.out.match(/RESULT (\{.*\})/);
      const oracle_detects_leak = m ? JSON.parse(m[1]).leak : null;

      const task = {
        task_id: `lookahead_${String(++id).padStart(3, "0")}`,
        bug_type: "lookahead_basis",
        variant,
        lookahead_bars: L,
        target_file: ENGINE,
        function: "runBacktest",
        clean_line: CLEAN,
        mutated_line: mutated,
        tests_pass,
        oracle_detects_leak,
        valid: oracle_detects_leak === true && tests_pass !== false,
      };
      if (task.valid) valid++;
      fs.writeFileSync(`leakbench/tasks/${task.task_id}.json`, JSON.stringify(task, null, 2));
      console.log(task.task_id, variant, "L=" + L, "tests_pass=" + tests_pass, "leak=" + oracle_detects_leak);
    }
  }
} finally {
  fs.writeFileSync(ENGINE, orig); // always restore the clean engine
}
console.log(`\n${valid}/${id} tasks valid (oracle flags leak, tests not failing). engine.ts restored.`);