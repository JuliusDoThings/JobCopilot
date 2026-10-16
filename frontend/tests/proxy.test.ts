// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import { POST } from "@/app/api/analyze/route";

const input = {
  cv_text: " CV fictif confidentiel ",
  job_text: " Annonce fictive confidentielle ",
};
const scored = {
  status: "scored",
  score: 50,
  matched_skills: ["python"],
  missing_skills: ["sql"],
  reason: null,
};
const unscored = {
  status: "not_scorable",
  score: null,
  matched_skills: [],
  missing_skills: [],
  reason: "no_explicit_required_skills",
};
function request(body: unknown = input) {
  return new Request("http://localhost:3000/api/analyze", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

afterEach(() => vi.clearAllTimers());

describe("proxy", () => {
  it.each([scored, { ...scored, score: 0 }, unscored])(
    "forwards valid states without coercion",
    async (result) => {
      const fetcher = vi.fn().mockResolvedValue(Response.json(result));
      vi.stubGlobal("fetch", fetcher);
      const response = await POST(request());
      expect(response.status).toBe(200);
      expect(await response.json()).toEqual(result);
      expect(response.headers.get("cache-control")).toBe("no-store");
      expect(fetcher).toHaveBeenCalledOnce();
      const [url, options] = fetcher.mock.calls[0];
      expect(url.toString()).toBe(
        "http://127.0.0.1:8000/api/v1/matching/analyze",
      );
      expect(options).toMatchObject({
        method: "POST",
        cache: "no-store",
        redirect: "error",
      });
      expect(JSON.parse(options.body)).toEqual({
        cv_text: input.cv_text.trim(),
        job_text: input.job_text.trim(),
      });
      expect(options.signal).toBeInstanceOf(AbortSignal);
    },
  );
  it("uses the server-only base URL", async () => {
    vi.stubEnv("FASTAPI_BASE_URL", "http://backend.internal:8000/prefix/");
    const fetcher = vi.fn().mockResolvedValue(Response.json(scored));
    vi.stubGlobal("fetch", fetcher);
    await POST(request());
    expect(fetcher.mock.calls[0][0].toString()).toBe(
      "http://backend.internal:8000/prefix/api/v1/matching/analyze",
    );
  });
  it.each([
    "invalid",
    "ftp://host",
    "http://user:secret@host",
    "http://host/?key=secret",
  ])("rejects invalid configuration", async (url) => {
    vi.stubEnv("FASTAPI_BASE_URL", url);
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const response = await POST(request());
    expect(response.status).toBe(503);
    expect(fetcher).not.toHaveBeenCalled();
    expect(await response.text()).not.toContain(url);
  });
  it.each([
    {},
    { ...input, extra: 1 },
    { ...input, cv_text: " " },
    { ...input, job_text: "x".repeat(20_001) },
    { ...input, cv_text: 1 },
  ])("rejects invalid input before fetch", async (body) => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    expect((await POST(request(body))).status).toBe(422);
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("rejects invalid JSON before fetch", async () => {
    const response = await POST(
      new Request("http://localhost/api/analyze", {
        method: "POST",
        body: "{",
      }),
    );
    expect(response.status).toBe(422);
  });
  it.each([422, 502, 503, 504, 401, 500])(
    "sanitizes backend error %i without retry",
    async (status) => {
      const fetcher = vi
        .fn()
        .mockResolvedValue(
          new Response("RAW-SECRET " + input.cv_text, { status }),
        );
      vi.stubGlobal("fetch", fetcher);
      const response = await POST(request());
      expect(response.status).toBe(
        [422, 502, 503, 504].includes(status) ? status : 502,
      );
      const text = await response.text();
      expect(text).not.toContain("RAW-SECRET");
      expect(text).not.toContain(input.cv_text.trim());
      expect(fetcher).toHaveBeenCalledOnce();
    },
  );
  it("sanitizes network errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("RAW-SECRET")));
    const response = await POST(request());
    expect(response.status).toBe(502);
    expect(await response.text()).not.toContain("RAW-SECRET");
  });
  it.each([
    { ...scored, score: null },
    { ...unscored, score: 0 },
    { secret: "RAW-SECRET" },
  ])("rejects invalid upstream payload", async (body) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(body)));
    expect((await POST(request())).status).toBe(502);
  });
  it("rejects invalid upstream JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("RAW-SECRET")),
    );
    const response = await POST(request());
    expect(response.status).toBe(502);
    expect(await response.text()).not.toContain("RAW-SECRET");
  });
  it("aborts at five minutes and clears its timer", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn(
      (_url, options) =>
        new Promise((_resolve, reject) => {
          options.signal.addEventListener("abort", () =>
            reject(new Error("aborted")),
          );
        }),
    );
    vi.stubGlobal("fetch", fetcher);
    const pending = POST(request());
    await vi.advanceTimersByTimeAsync(300_000);
    expect((await pending).status).toBe(504);
    expect(fetcher).toHaveBeenCalledOnce();
    expect(vi.getTimerCount()).toBe(0);
  });
  it("clears the timeout after success", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(scored)));
    await POST(request());
    expect(vi.getTimerCount()).toBe(0);
  });
});
