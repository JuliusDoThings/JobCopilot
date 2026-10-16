import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import corpus from "@/lib/dev-bench/corpus.json";
import Bench from "@/app/dev/valorization/bench";
import type { Scenario } from "@/lib/dev-bench/types";
const scenarios = corpus.scenarios.slice(0, 2) as Scenario[];
function renderBench() { render(<Bench scenarios={scenarios} corpusVersion={corpus.version} />); }
it("starts non-executed with visible inputs and expected outcomes", () => {
  renderBench();
  expect(screen.getByRole("status")).toHaveTextContent("0 conformes · 0 écarts · 2 non exécutés");
  expect(screen.getAllByText("Non exécuté")).toHaveLength(2);
  expect(screen.getAllByText(scenarios[0].input.cv_text).length).toBeGreaterThan(0);
  expect(fetch).not.toHaveBeenCalled();
});
it("shows real response and differences, keeping unavailable cases non-executed", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(Response.json({ scenarioId: "VAL-001", startedAt: "2026-10-16T16:00:00Z", durationMs: 8, httpStatus: 200, outcome: "executed", actual: [{ skill: "Python", status: "needs_clarification", evidence: scenarios[0].input.cv_text, suggestion: null, clarification_question: "Votre rôle ?" }], error: null })).mockRejectedValueOnce(new Error("SECRET")));
  renderBench(); fireEvent.click(screen.getByRole("button", { name: "Exécuter tous les scénarios" }));
  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("0 conformes · 1 écarts · 1 non exécutés"));
  expect(screen.getByText("Détails de l’écart")).toBeVisible();
  expect(screen.queryByText("SECRET")).not.toBeInTheDocument();
});
it("clears stale success and blocks concurrent runs, then replaces it on failure", async () => {
  const actual = scenarios[0].expected.map(e => ({ skill: e.skill, status: e.status, evidence: e.evidence, suggestion: e.suggestion, clarification_question: null }));
  const fetcher = vi.fn().mockResolvedValueOnce(Response.json({ scenarioId: "VAL-001", startedAt: "now", durationMs: 1, httpStatus: 200, outcome: "executed", actual, error: null }));
  vi.stubGlobal("fetch", fetcher);
  renderBench(); fireEvent.click(screen.getByRole("button", { name: "Exécuter VAL-001" }));
  expect(await screen.findByText("Conforme")).toBeVisible();
  let reject!: (error: Error) => void;
  fetcher.mockImplementationOnce(() => new Promise((_resolve, fail) => { reject = fail; }));
  fireEvent.click(screen.getByRole("button", { name: "Exécuter VAL-001" }));
  expect(screen.queryByText("Conforme")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Exécuter tous les scénarios" })).toBeDisabled();
  reject(new Error("unavailable"));
  await waitFor(() => expect(screen.getByRole("button", { name: "Exécuter VAL-001" })).toBeEnabled());
  expect(fetcher).toHaveBeenCalledTimes(2);
  expect(screen.queryByText("Conforme")).not.toBeInTheDocument();
});
it("exports unexecuted scenarios explicitly, without fabricating successful evidence", async () => {
  const create = vi.fn().mockReturnValue("blob:test");
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: create, revokeObjectURL: vi.fn() }));
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  renderBench(); fireEvent.click(screen.getByRole("button", { name: "Exporter les preuves JSON" }));
  expect(create).toHaveBeenCalledOnce();
  expect(create.mock.calls[0][0]).toBeInstanceOf(Blob);
  const text = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result)); reader.onerror = reject;
    reader.readAsText(create.mock.calls[0][0]);
  });
  const exported = JSON.parse(text);
  expect(exported.corpusVersion).toBe(corpus.version);
  expect(exported.scenarios.every((s: { execution: unknown; comparison: { status: string } }) => s.execution === null && s.comparison.status === "non_execute")).toBe(true);
  expect(within(screen.getAllByRole("article")[0]).getByText("Non exécuté")).toBeVisible();
});
