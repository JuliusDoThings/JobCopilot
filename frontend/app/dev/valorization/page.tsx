import { notFound } from "next/navigation";
import corpus from "@/lib/dev-bench/corpus.json";
import { benchEnabled } from "@/lib/dev-bench/access";
import type { Scenario } from "@/lib/dev-bench/types";
import Bench from "./bench";

export const dynamic = "force-dynamic";
export default function BenchPage() {
  if (!benchEnabled()) notFound();
  return <Bench scenarios={corpus.scenarios as Scenario[]} corpusVersion={corpus.version} />;
}
