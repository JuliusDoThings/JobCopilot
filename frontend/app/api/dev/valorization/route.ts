import corpus from "@/lib/dev-bench/corpus.json";
import { benchEnabled, localRequest } from "@/lib/dev-bench/access";
import { executeScenario } from "@/lib/dev-bench/execute";
import type { Scenario } from "@/lib/dev-bench/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const headers = { "Cache-Control": "no-store" };
export async function POST(request: Request): Promise<Response> {
  if (!benchEnabled()) return new Response(null, { status: 404, headers });
  if (!localRequest(request)) return new Response(null, { status: 403, headers });
  let body: unknown;
  try {
    const text = await request.text();
    if (text.length > 200) return new Response(null, { status: 422, headers });
    body = JSON.parse(text);
  } catch { return new Response(null, { status: 422, headers }); }
  if (!body || typeof body !== "object" || Array.isArray(body) || Object.keys(body).length !== 1 || !("scenarioId" in body)) return new Response(null, { status: 422, headers });
  const scenario = (corpus.scenarios as Scenario[]).find(s => s.id === body.scenarioId);
  if (!scenario) return new Response(null, { status: 422, headers });
  return Response.json(await executeScenario(scenario), { headers });
}
