// Server-only gate: never use a NEXT_PUBLIC variable for diagnostic access.
export function benchEnabled(): boolean {
  return process.env.NODE_ENV === "development" && process.env.JOB_COPILOT_DEV_BENCH === "1";
}
export function localRequest(request: Request): boolean {
  try {
    const url = new URL(request.url);
    const origin = new URL(request.headers.get("origin") || "");
    // Next may reconstruct request.url with localhost while the browser uses
    // 127.0.0.1. Compare against the real Host header, never forwarded headers.
    const host = request.headers.get("host") || url.host;
    const publicHost = new URL(`${url.protocol}//${host}`).hostname;
    return ["127.0.0.1", "localhost", "[::1]"].includes(publicHost) &&
      ["127.0.0.1", "localhost", "[::1]"].includes(origin.hostname) &&
      origin.host === host && origin.protocol === url.protocol &&
      origin.origin === request.headers.get("origin");
  } catch { return false; }
}
