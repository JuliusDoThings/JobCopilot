"use client";
import { useRef, useState } from "react";
import { compare, isExecution } from "@/lib/dev-bench/compare";
import type { Execution, Scenario } from "@/lib/dev-bench/types";
import styles from "./bench.module.css";

const labels = { conforme: "Conforme", ecart: "Écart", non_execute: "Non exécuté" };
export default function Bench({ scenarios, corpusVersion }: { scenarios: Scenario[]; corpusVersion: string }) {
  const [runs, setRuns] = useState<Record<string, Execution>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const lock = useRef(false);
  async function run(selected: Scenario[]) {
    if (lock.current) return;
    lock.current = true;
    // Remove stale green statuses before starting a new attempt.
    setRuns(previous => Object.fromEntries(Object.entries(previous).filter(([id]) => !selected.some(s => s.id === id))));
    try {
      for (const scenario of selected) {
        setBusy(scenario.id);
        const start = Date.now();
        let execution: Execution;
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 8000);
        try {
          const response = await fetch("/api/dev/valorization", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scenarioId: scenario.id }), cache: "no-store", signal: controller.signal });
          if (!response.ok) throw new Error("proxy");
          const value = await response.json();
          if (!isExecution(value, scenario.id)) throw new Error("contract");
          execution = value;
        } catch {
          execution = { scenarioId: scenario.id, startedAt: new Date(start).toISOString(), durationMs: Date.now() - start, httpStatus: null, outcome: "not_executed", actual: null, error: "Banc inaccessible, délai dépassé ou réponse invalide. Vérifiez les deux serveurs locaux et l’activation du banc." };
        } finally { clearTimeout(timer); }
        setRuns(previous => ({ ...previous, [scenario.id]: execution }));
      }
    } finally { lock.current = false; setBusy(null); }
  }
  function download() {
    const report = { corpusVersion, exportedAt: new Date().toISOString(), endpoint: "/api/v1/cv/valorization", scenarios: scenarios.map(s => ({ ...s, execution: runs[s.id] ?? null, comparison: compare(s, runs[s.id]) })) };
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = "job-copilot-valorization-report.json"; anchor.click(); URL.revokeObjectURL(url);
  }
  const totals = scenarios.map(s => compare(s, runs[s.id]).status);
  return <main className={styles.shell}>
    <p className={styles.kicker}>JOB COPILOT · DÉVELOPPEMENT LOCAL</p>
    <h1>Banc d’essai de valorisation</h1>
    <p>Comparez les attentes métier aux réponses de la véritable API FastAPI. Données entièrement synthétiques. Corpus {corpusVersion}.</p>
    <p>Une citation doit rester identique au CV. Les formulations naturelles non reconnues restent des écarts visibles, sans changer les attentes.</p>
    <div className={styles.toolbar}>
      <button disabled={!!busy} onClick={() => run(scenarios)}>Exécuter tous les scénarios</button>
      <button disabled={!!busy} onClick={download}>Exporter les preuves JSON</button>
    </div>
    <p role="status" aria-live="polite">{totals.filter(s => s === "conforme").length} conformes · {totals.filter(s => s === "ecart").length} écarts · {totals.filter(s => s === "non_execute").length} non exécutés{busy ? ` · En cours : ${busy}` : ""}</p>
    {scenarios.map(scenario => {
      const execution = runs[scenario.id];
      const comparison = compare(scenario, execution);
      return <article key={scenario.id} className={styles.card} aria-labelledby={scenario.id}>
        <div className={styles.heading}><h2 id={scenario.id}>{scenario.id} · {scenario.title}</h2><strong className={styles[comparison.status]}>{labels[comparison.status]}</strong></div>
        <p>{scenario.rationale}</p>
        <div className={styles.columns}>
          <section><h3>CV synthétique</h3><pre>{scenario.input.cv_text}</pre><h3>Compétences ciblées</h3><p>{scenario.input.target_skills.join(", ")}</p></section>
          <section><h3>Résultat attendu</h3>{scenario.expected.map((e, index) => <div key={index}><p><b>{e.skill}</b> : {e.status} · Question {e.questionRequired ? "requise" : "interdite"}</p><p>Preuve : {e.evidence ?? "aucune"}</p><p>Suggestion : {e.suggestion ?? "aucune"}</p></div>)}</section>
        </div>
        <section><h3>Résultat réel de l’API</h3>{execution ? <><p>Exécution : {execution.startedAt} · {execution.durationMs} ms · HTTP {execution.httpStatus ?? "aucune réponse"}</p>{execution.error && <p className={styles.error}>{execution.error}</p>}<pre>{execution.actual === null ? "Aucun résultat métier exploitable." : JSON.stringify(execution.actual, null, 2)}</pre></> : <p>Aucun appel effectué pour ce scénario.</p>}</section>
        {comparison.differences.length > 0 && <section><h3>{comparison.status === "ecart" ? "Détails de l’écart" : "Diagnostic"}</h3><ul>{comparison.differences.map((d, i) => <li key={i}>{d}</li>)}</ul></section>}
        <button disabled={!!busy} onClick={() => run([scenario])}>{busy === scenario.id ? "Exécution en cours…" : `Exécuter ${scenario.id}`}</button>
      </article>;
    })}
  </main>;
}
