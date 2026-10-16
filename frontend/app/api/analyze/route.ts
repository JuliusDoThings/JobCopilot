import { errorMessage, isAnalyzeResult, parseInput } from "@/lib/analyze";

export const runtime = "nodejs";
export const maxDuration = 300;

const TIMEOUT_MS = 300_000;
const headers = { "Cache-Control": "no-store" };

function fail(status: number) {
  return Response.json({ error: errorMessage(status) }, { status, headers });
}

export async function POST(request: Request): Promise<Response> {
  let raw: unknown;
  try {
    raw = await request.json();
  } catch {
    return fail(422);
  }
  const input = parseInput(raw);
  if (!input) return fail(422);

  let endpoint: URL;
  try {
    const base = new URL(
      process.env.FASTAPI_BASE_URL || "http://127.0.0.1:8000",
    );
    if (
      !["http:", "https:"].includes(base.protocol) ||
      base.username ||
      base.password ||
      base.search ||
      base.hash
    )
      return fail(503);
    endpoint = new URL(
      `${base.toString().replace(/\/$/, "")}/api/v1/matching/analyze`,
    );
  } catch {
    return fail(503);
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const upstream = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
      signal: controller.signal,
      cache: "no-store",
      redirect: "error",
    });
    if (!upstream.ok)
      return fail(
        [422, 502, 503, 504].includes(upstream.status) ? upstream.status : 502,
      );
    const result: unknown = await upstream.json();
    if (!isAnalyzeResult(result)) return fail(502);
    return Response.json(result, { headers });
  } catch {
    return fail(controller.signal.aborted ? 504 : 502);
  } finally {
    clearTimeout(timeout);
  }
}
