import type { Execution, Scenario } from "./types";
import { isRecommendations } from "./compare";

export function getApiEndpoint(): string | null {
  const base = process.env.JOB_COPILOT_BENCH_API_BASE || "http://127.0.0.1:8000";
  // Exact server-side allowlist: no arbitrary URL, credentials or query strings.
  if (!["http://127.0.0.1:8000", "http://backend:8000"].includes(base)) return null;
  return `${base}/api/v1/cv/valorization`;
}
const MAX_BYTES = 64_000;
async function boundedJson(response: Response): Promise<unknown> {
  if (!response.body) throw new Error("invalid");
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let length = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      length += value.length;
      if (length > MAX_BYTES) throw new Error("oversized");
      chunks.push(value);
    }
  } finally { await reader.cancel(); }
  const bytes = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  return JSON.parse(new TextDecoder().decode(bytes));
}
export async function executeScenario(scenario: Scenario): Promise<Execution> {
  const started = Date.now();
  const result: Execution = { scenarioId: scenario.id, startedAt: new Date(started).toISOString(), durationMs: 0, httpStatus: null, outcome: "not_executed", actual: null, error: null };
  const endpoint = getApiEndpoint();
  if (!endpoint) {
    result.error = "Configuration locale du banc invalide.";
    return result;
  }
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch(endpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(scenario.input), cache: "no-store", redirect: "error", signal: controller.signal });
    result.httpStatus = response.status;
    if (response.status !== 200) {
      await response.body?.cancel();
      result.error = `API : HTTP ${response.status}. Corps d’erreur masqué.`;
    } else {
      result.outcome = "executed";
      try {
        const actual = await boundedJson(response);
        if (isRecommendations(actual)) result.actual = actual;
        else result.error = "Réponse API hors contrat ; contenu masqué.";
      } catch { result.error = controller.signal.aborted ? "Délai de lecture API dépassé (5 s)." : "Réponse API illisible ou trop volumineuse ; contenu masqué."; }
    }
  } catch {
    result.error = controller.signal.aborted ? "API : délai dépassé (5 s)." : "API indisponible ou connexion refusée.";
  } finally {
    clearTimeout(timeout);
    result.durationMs = Date.now() - started;
  }
  return result;
}
