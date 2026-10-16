import { expect, it, vi } from "vitest";
vi.mock("next/navigation", () => ({ notFound: () => { throw new Error("NOT_FOUND"); } }));
import BenchPage from "@/app/dev/valorization/page";
it.each(["production", "test"])("does not render diagnostic corpus in %s", environment => {
  vi.stubEnv("NODE_ENV", environment); vi.stubEnv("JOB_COPILOT_DEV_BENCH", "1");
  expect(() => BenchPage()).toThrow("NOT_FOUND");
});
it("does not render without explicit opt-in", () => {
  vi.stubEnv("NODE_ENV", "development"); vi.stubEnv("JOB_COPILOT_DEV_BENCH", "");
  expect(() => BenchPage()).toThrow("NOT_FOUND");
});
it("renders development-only bench when explicitly enabled", () => {
  vi.stubEnv("NODE_ENV", "development"); vi.stubEnv("JOB_COPILOT_DEV_BENCH", "1");
  expect(BenchPage()).toBeTruthy();
});
