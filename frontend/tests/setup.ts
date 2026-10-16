import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

beforeEach(() => {
  vi.stubEnv("FASTAPI_BASE_URL", "");
  // Every test starts with external HTTP forbidden; individual tests install mocks.
  vi.stubGlobal(
    "fetch",
    vi.fn(() => {
      throw new Error("External network is forbidden in tests");
    }),
  );
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.useRealTimers();
});
