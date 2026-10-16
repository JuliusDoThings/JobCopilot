import type { Comparison, Execution, Recommendation, Scenario } from "./types";

const keys = ["skill", "status", "evidence", "suggestion", "clarification_question"].sort();
export function isRecommendations(value: unknown): value is Recommendation[] {
  return Array.isArray(value) && value.length <= 100 && value.every((item) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) return false;
    const r = item as Record<string, unknown>;
    return JSON.stringify(Object.keys(r).sort()) === JSON.stringify(keys) &&
      typeof r.skill === "string" && r.skill.length <= 200 &&
      typeof r.status === "string" && ["suggested", "needs_clarification", "no_evidence"].includes(r.status) &&
      [r.evidence, r.suggestion, r.clarification_question].every(v => v === null || (typeof v === "string" && v.length <= 20_000));
  });
}
export function isExecution(value: unknown, scenarioId: string): value is Execution {
  if (!value || typeof value !== "object") return false;
  const e = value as Record<string, unknown>;
  return e.scenarioId === scenarioId &&
    typeof e.outcome === "string" && ["executed", "not_executed"].includes(e.outcome) &&
    typeof e.startedAt === "string" &&
    typeof e.durationMs === "number" && Number.isFinite(e.durationMs) && e.durationMs >= 0 &&
    (e.httpStatus === null || (Number.isInteger(e.httpStatus) && Number(e.httpStatus) >= 100 && Number(e.httpStatus) <= 599)) &&
    (e.error === null || typeof e.error === "string") && "actual" in e;
}
export function compare(scenario: Scenario, execution?: Execution): Comparison {
  if (!execution || execution.outcome !== "executed") return {
    status: "non_execute", differences: [execution?.error || "Aucune réponse métier de l’API évaluée."],
  };
  const differences: string[] = [];
  if (execution.error) differences.push(execution.error);
  if (execution.scenarioId !== scenario.id) differences.push("Identifiant de scénario différent.");
  if (execution.httpStatus !== 200) differences.push(`HTTP attendu 200, reçu ${execution.httpStatus}.`);
  if (!isRecommendations(execution.actual)) return {
    status: "ecart", differences: [...differences, "Réponse incompatible avec le contrat de valorisation."],
  };
  const actual = execution.actual;
  if (actual.length !== scenario.expected.length) differences.push(`Nombre de résultats : attendu ${scenario.expected.length}, reçu ${actual.length}.`);
  scenario.expected.forEach((expected, index) => {
    const result = actual[index];
    if (!result) { differences.push(`Résultat ${index + 1} absent.`); return; }
    for (const field of ["skill", "status", "evidence", "suggestion"] as const) {
      if (result[field] !== expected[field]) differences.push(`${expected.skill} · ${field} : attendu ${JSON.stringify(expected[field])}, reçu ${JSON.stringify(result[field])}.`);
    }
    const hasQuestion = typeof result.clarification_question === "string" && !!result.clarification_question.trim();
    if (hasQuestion !== expected.questionRequired || (!expected.questionRequired && result.clarification_question !== null)) differences.push(`${expected.skill} · question de clarification ${expected.questionRequired ? "requise" : "interdite"}.`);
    if (result.evidence !== null && (!result.evidence.trim() || !scenario.input.cv_text.includes(result.evidence))) differences.push(`${expected.skill} · preuve absente du CV source.`);
    if (result.suggestion !== null && (result.suggestion !== result.evidence || !scenario.input.cv_text.includes(result.suggestion))) differences.push(`${expected.skill} · suggestion non identique à une preuve du CV : risque d’invention.`);
  });
  return { status: differences.length ? "ecart" : "conforme", differences };
}
