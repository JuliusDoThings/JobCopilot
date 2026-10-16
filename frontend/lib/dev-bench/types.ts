export type Recommendation = {
  skill: string;
  status: "suggested" | "needs_clarification" | "no_evidence";
  evidence: string | null;
  suggestion: string | null;
  clarification_question: string | null;
};
export type Expected = Omit<Recommendation, "clarification_question"> & { questionRequired: boolean };
export type Scenario = {
  id: string;
  title: string;
  rationale: string;
  input: { cv_text: string; target_skills: string[] };
  expected: Expected[];
};
export type Execution = {
  scenarioId: string;
  startedAt: string;
  durationMs: number;
  httpStatus: number | null;
  outcome: "executed" | "not_executed";
  actual: unknown;
  error: string | null;
};
export type Comparison = { status: "conforme" | "ecart" | "non_execute"; differences: string[] };
