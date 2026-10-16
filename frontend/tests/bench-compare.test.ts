import { describe, expect, it } from "vitest";
import corpus from "@/lib/dev-bench/corpus.json";
import { compare } from "@/lib/dev-bench/compare";
import type { Execution, Scenario } from "@/lib/dev-bench/types";
const scenarios = corpus.scenarios as Scenario[];
function success(s: Scenario): Execution {
  return { scenarioId: s.id, startedAt: "2026-10-16T16:00:00Z", durationMs: 3, httpStatus: 200, outcome: "executed", error: null, actual: s.expected.map(({ questionRequired, ...expected }) => ({ ...expected, clarification_question: questionRequired ? "Dans quel contexte ?" : null })) };
}
describe("independent business comparison", () => {
  it("keeps corpus IDs unique and expectations tied to source, not service output", () => {
    expect(new Set(scenarios.map(s => s.id)).size).toBe(scenarios.length);
    expect(scenarios).toHaveLength(12);
    for (const s of scenarios) {
      expect(s.expected.map(e => e.skill)).toEqual(s.input.target_skills);
      for (const e of s.expected) if (e.evidence) expect(s.input.cv_text).toContain(e.evidence);
    }
    expect(scenarios.find(s => s.id === "VAL-007")!.expected[0].status).toBe("suggested");
  });
  it.each(scenarios)("accepts explicit expected contract for $id", s => {
    expect(compare(s, success(s)).status).toBe("conforme");
  });
  it("never accepts missing or unsuccessful execution", () => {
    const s = scenarios[0];
    expect(compare(s).status).toBe("non_execute");
    expect(compare(s, { ...success(s), outcome: "not_executed", error: "API indisponible" }).status).toBe("non_execute");
    expect(compare(s, { ...success(s), httpStatus: 503 }).status).toBe("ecart");
    expect(compare(s, { ...success(s), scenarioId: "other" }).status).toBe("ecart");
  });
  it.each([
    { status: "needs_clarification", suggestion: null, clarification_question: "Précisez ?" },
    { evidence: "Invention" }, { suggestion: "Expert depuis 10 ans, +50 %" },
    { clarification_question: "Question inattendue ?" }, { skill: "Java" },
  ])("detects status, provenance, invention, question and skill differences", patch => {
    const s = scenarios[0]; const e = success(s);
    e.actual = [{ ...(e.actual as object[])[0], ...patch }];
    expect(compare(s, e).status).toBe("ecart");
    expect(compare(s, e).differences.length).toBeGreaterThan(0);
  });
  it.each([null, {}, [], [{ secret: "never display" }], "not JSON"])("rejects incomplete or invalid API results", actual => {
    expect(compare(scenarios[0], { ...success(scenarios[0]), actual }).status).toBe("ecart");
  });
  it("requires a real clarification question", () => {
    const s = scenarios[1]; const e = success(s);
    e.actual = [{ ...(e.actual as object[])[0], clarification_question: " " }];
    expect(compare(s, e).status).toBe("ecart");
  });
  it("detects natural wording limitation rather than blessing current behavior", () => {
    const s = scenarios[6]; const e = success(s);
    e.actual = [{ ...(e.actual as object[])[0], status: "needs_clarification", suggestion: null, clarification_question: "Votre rôle ?" }];
    expect(compare(s, e).status).toBe("ecart");
  });
});
