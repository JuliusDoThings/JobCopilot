// Uses the same comparator/runner as the UI, against the real local FastAPI.
import { readFile, writeFile } from "node:fs/promises";
import ts from "typescript";
import process from "node:process";
import console from "node:console";
import { URL } from "node:url";
import { Buffer } from "node:buffer";

if (process.env.NODE_ENV === "production" || process.env.JOB_COPILOT_DEV_BENCH !== "1") {
  console.error("Development only: set JOB_COPILOT_DEV_BENCH=1.");
  process.exit(2);
}
const root = new URL("../", import.meta.url);
const corpus = JSON.parse(await readFile(new URL("lib/dev-bench/corpus.json", root), "utf8"));
const comparator = await readFile(new URL("lib/dev-bench/compare.ts", root), "utf8");
const runner = (await readFile(new URL("lib/dev-bench/execute.ts", root), "utf8")).replace('import { isRecommendations } from "./compare";', "");
const { outputText } = ts.transpileModule(comparator + "\n" + runner, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
const { compare, executeScenario } = await import("data:text/javascript;base64," + Buffer.from(outputText).toString("base64"));
const report = { corpusVersion: corpus.version, exportedAt: new Date().toISOString(), endpoint: "http://127.0.0.1:8000/api/v1/cv/valorization", scenarios: [] };
for (const scenario of corpus.scenarios) {
  const execution = await executeScenario(scenario);
  const comparison = compare(scenario, execution);
  report.scenarios.push({ ...scenario, execution, comparison });
  console.log(`${scenario.id}: ${comparison.status}${execution.error ? " · " + execution.error : ""}`);
}
const output = process.argv[2] || "valorization-report.json";
await writeFile(output, JSON.stringify(report, null, 2) + "\n");
console.log(`Evidence: ${output}`);
process.exitCode = report.scenarios.some(s => s.comparison.status === "non_execute") ? 2 : report.scenarios.some(s => s.comparison.status === "ecart") ? 1 : 0;
