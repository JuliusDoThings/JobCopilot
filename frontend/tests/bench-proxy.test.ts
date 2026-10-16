// @vitest-environment node
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { POST } from "@/app/api/dev/valorization/route";
import corpus from "@/lib/dev-bench/corpus.json";
const scenario = corpus.scenarios[0];
const actual = [{ skill: "Python", status: "suggested", evidence: scenario.input.cv_text, suggestion: scenario.input.cv_text, clarification_question: null }];
function request(body: unknown = { scenarioId: scenario.id }, origin = "http://localhost:3000", url = "http://localhost:3000/api/dev/valorization") {
  return new Request(url, { method: "POST", headers: { origin }, body: JSON.stringify(body) });
}
beforeEach(() => { vi.stubEnv("NODE_ENV", "development"); vi.stubEnv("JOB_COPILOT_DEV_BENCH", "1"); });
afterEach(() => vi.clearAllTimers());
it.each(["production", "test"])("disables diagnostics in %s even when enabled", async environment => {
  vi.stubEnv("NODE_ENV", environment);
  expect((await POST(request())).status).toBe(404);
  expect(fetch).not.toHaveBeenCalled();
});
it("requires explicit activation", async () => {
  vi.stubEnv("JOB_COPILOT_DEV_BENCH", "");
  expect((await POST(request())).status).toBe(404);
  expect(fetch).not.toHaveBeenCalled();
});
it.each([
  ["https://evil.example", "http://localhost:3000/api/dev/valorization"],
  ["http://example.com", "http://example.com/api/dev/valorization"],
  ["", "http://localhost:3000/api/dev/valorization"],
])("blocks cross-origin and non-loopback requests", async (origin, url) => {
  expect((await POST(request(undefined, origin, url))).status).toBe(403);
  expect(fetch).not.toHaveBeenCalled();
});
it.each([{ scenarioId: "unknown" }, { scenarioId: scenario.id, cv_text: "secret" }, {}, null, []])("only permits corpus IDs", async body => {
  expect((await POST(request(body))).status).toBe(422);
  expect(fetch).not.toHaveBeenCalled();
});
it("rejects invalid JSON", async () => {
  expect((await POST(new Request("http://localhost:3000/api/dev/valorization", { method: "POST", headers: { origin: "http://localhost:3000" }, body: "{" }))).status).toBe(422);
});
it("calls actual fixed FastAPI route with versioned input and exports sanitized evidence", async () => {
  const fetcher = vi.fn().mockResolvedValue(Response.json(actual)); vi.stubGlobal("fetch", fetcher);
  const response = await POST(request()); const result = await response.json();
  expect(result).toMatchObject({ scenarioId: scenario.id, httpStatus: 200, outcome: "executed", actual, error: null });
  expect(result.startedAt).toMatch(/^\d{4}-/); expect(result.durationMs).toBeGreaterThanOrEqual(0);
  expect(response.headers.get("cache-control")).toBe("no-store");
  expect(fetcher).toHaveBeenCalledWith("http://127.0.0.1:8000/api/v1/cv/valorization", expect.objectContaining({ body: JSON.stringify(scenario.input), redirect: "error", cache: "no-store" }));
});
it("records API unavailable without false conformity or secret leakage", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("SECRET_TOKEN")));
  const result = await (await POST(request())).json();
  expect(result.outcome).toBe("not_executed"); expect(result.actual).toBeNull();
  expect(result.error).toContain("indisponible"); expect(JSON.stringify(result)).not.toContain("SECRET_TOKEN");
});
it("records HTTP status without exposing upstream errors", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("SECRET_TOKEN", { status: 500 })));
  const result = await (await POST(request())).json();
  expect(result).toMatchObject({ outcome: "not_executed", httpStatus: 500, actual: null });
  expect(JSON.stringify(result)).not.toContain("SECRET_TOKEN");
});
it.each(["SECRET_TOKEN", JSON.stringify({ secret: "SECRET_TOKEN" }), "x".repeat(64001)])("marks malformed/oversized responses as executed contract errors", async payload => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(payload)));
  const result = await (await POST(request())).json();
  expect(result).toMatchObject({ outcome: "executed", httpStatus: 200, actual: null });
  expect(result.error).toBeTruthy(); expect(JSON.stringify(result)).not.toContain("SECRET_TOKEN");
});
it("aborts at 5 seconds and clears the timer", async () => {
  vi.useFakeTimers();
  vi.stubGlobal("fetch", vi.fn((_url, options) => new Promise((_resolve, reject) => options.signal.addEventListener("abort", () => reject(new Error("SECRET"))))));
  const pending = POST(request());
  await vi.advanceTimersByTimeAsync(5000);
  expect(await (await pending).json()).toMatchObject({ outcome: "not_executed", error: "API : délai dépassé (5 s)." });
  expect(vi.getTimerCount()).toBe(0);
});

it("supports Next's internal localhost URL with a real loopback Host header", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(actual)));
  const response = await POST(new Request("http://localhost:3000/api/dev/valorization", { method: "POST", headers: { host: "127.0.0.1:3000", origin: "http://127.0.0.1:3000" }, body: JSON.stringify({ scenarioId: scenario.id }) }));
  expect(response.status).toBe(200);
});
it("rejects a mismatched real Host header", async () => {
  const response = await POST(new Request("http://localhost:3000/api/dev/valorization", { method: "POST", headers: { host: "127.0.0.1:3000", origin: "http://localhost:3000" }, body: JSON.stringify({ scenarioId: scenario.id }) }));
  expect(response.status).toBe(403);
  expect(fetch).not.toHaveBeenCalled();
});
