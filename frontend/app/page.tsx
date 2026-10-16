"use client";

import Link from "next/link";
import { useRef, useState, type FormEvent } from "react";
import {
  errorMessage,
  fieldError,
  isAnalyzeResult,
  textLength,
  type AnalyzeResult,
} from "@/lib/analyze";

export default function Home() {
  const [cv, setCv] = useState("");
  const [job, setJob] = useState("");
  const [errors, setErrors] = useState<{ cv?: string; job?: string }>({});
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const submitting = useRef(false);

  function edit(kind: "cv" | "job", value: string) {
    if (kind === "cv") setCv(value);
    else setJob(value);
    setErrors((previous) => ({ ...previous, [kind]: undefined }));
    setResult(null);
    setError(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting.current) return;
    setResult(null);
    setError(null);
    const cvError = fieldError(cv, "Le CV");
    const jobError = fieldError(job, "L’offre");
    setErrors({ cv: cvError ?? undefined, job: jobError ?? undefined });
    if (cvError || jobError) {
      document.getElementById(cvError ? "cv" : "job")?.focus();
      return;
    }
    submitting.current = true;
    setLoading(true);
    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cv_text: cv.trim(), job_text: job.trim() }),
        cache: "no-store",
      });
      if (!response.ok) {
        setError(errorMessage(response.status));
        return;
      }
      const data: unknown = await response.json();
      if (!isAnalyzeResult(data)) {
        setError(errorMessage(502));
        return;
      }
      setResult(data);
    } catch {
      setError(
        "La connexion a été interrompue. Vérifiez votre connexion et réessayez.",
      );
    } finally {
      submitting.current = false;
      setLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="header">
        <Link className="brand" href="/" aria-label="Job Copilot, accueil">
          <span className="brand-icon" aria-hidden="true">
            ↗
          </span>{" "}
          Job Copilot
        </Link>
        <span className="prototype">Prototype · Analyse de compétences</span>
      </header>
      <main id="main">
        <section className="intro" aria-labelledby="page-title">
          <p className="eyebrow">VOTRE PROCHAINE ÉTAPE, PLUS CLAIRE</p>
          <h1 id="page-title">
            Votre profil.
            <br />
            Leurs attentes.<span> Faisons le point.</span>
          </h1>
          <p className="lead">
            Comparez votre CV à une offre pour repérer les compétences que vous
            partagez et celles qu’il reste à explorer.
          </p>
        </section>

        <form onSubmit={submit} noValidate aria-busy={loading}>
          <div className="editor-grid">
            <section className="editor" aria-labelledby="cv-label">
              <div className="editor-heading">
                <span className="step" aria-hidden="true">
                  01
                </span>
                <div>
                  <label id="cv-label" htmlFor="cv">
                    Votre CV
                  </label>
                  <p>Votre parcours, en version texte.</p>
                </div>
              </div>
              <textarea
                id="cv"
                name="cv_text"
                value={cv}
                onChange={(e) => edit("cv", e.target.value)}
                disabled={loading}
                required
                aria-invalid={!!errors.cv}
                aria-describedby={`cv-hint${errors.cv ? " cv-error" : ""}`}
                placeholder="Collez ici le texte de votre CV…"
              />
              <div className="editor-footer" id="cv-hint">
                <span>Texte uniquement · obligatoire</span>
                <span>{textLength(cv).toLocaleString("fr-FR")} / 20 000</span>
              </div>
              {errors.cv && (
                <p id="cv-error" className="field-error" role="alert">
                  {errors.cv}
                </p>
              )}
            </section>
            <section className="editor" aria-labelledby="job-label">
              <div className="editor-heading">
                <span className="step" aria-hidden="true">
                  02
                </span>
                <div>
                  <label id="job-label" htmlFor="job">
                    L’offre d’emploi
                  </label>
                  <p>Le poste qui vous intéresse.</p>
                </div>
              </div>
              <textarea
                id="job"
                name="job_text"
                value={job}
                onChange={(e) => edit("job", e.target.value)}
                disabled={loading}
                required
                aria-invalid={!!errors.job}
                aria-describedby={`job-hint${errors.job ? " job-error" : ""}`}
                placeholder="Collez ici le texte de l’annonce…"
              />
              <div className="editor-footer" id="job-hint">
                <span>Texte uniquement · obligatoire</span>
                <span>{textLength(job).toLocaleString("fr-FR")} / 20 000</span>
              </div>
              {errors.job && (
                <p id="job-error" className="field-error" role="alert">
                  {errors.job}
                </p>
              )}
            </section>
          </div>
          <div className="submit-row">
            <p>
              Les textes sont transmis pour l’analyse,
              <br />
              sans sauvegarde dans ce navigateur.
            </p>
            <button type="submit" disabled={loading}>
              {loading ? "Analyse en cours…" : "Analyser la compatibilité"}
              <span aria-hidden="true">{loading ? "◌" : "↗"}</span>
            </button>
          </div>
          <p className="cost-note">
            Une analyse réelle peut déclencher deux extractions Azure
            facturables. Utilisez des textes fictifs pour essayer ce prototype.
          </p>
        </form>

        <div aria-live="polite" aria-atomic="true">
          {loading && (
            <p className="loading" role="status">
              Nous comparons les compétences. L’analyse peut prendre plusieurs
              minutes.
            </p>
          )}
          {error && (
            <div className="error-box" role="alert">
              <strong>L’analyse n’a pas abouti</strong>
              <p>{error}</p>
            </div>
          )}
          {result?.status === "not_scorable" && (
            <section className="results" aria-labelledby="result-title">
              <p className="eyebrow">VOTRE ANALYSE</p>
              <h2 id="result-title">Pas de score à calculer</h2>
              <p>
                Aucune compétence explicitement obligatoire n’a été identifiée
                dans cette offre. Cela ne signifie pas que votre profil ne
                convient pas.
              </p>
            </section>
          )}
          {result?.status === "scored" && (
            <section className="results" aria-labelledby="result-title">
              <div className="result-heading">
                <div>
                  <p className="eyebrow">VOTRE ANALYSE</p>
                  <h2 id="result-title">Les compétences, côte à côte.</h2>
                </div>
                <div className="score">
                  <strong>
                    {result.score.toLocaleString("fr-FR", {
                      maximumFractionDigits: 2,
                    })}{" "}
                    %
                  </strong>
                  <span>des exigences identifiées couvertes</span>
                </div>
              </div>
              <div className="skill-grid">
                <SkillList
                  title="Compétences présentes"
                  skills={result.matched_skills}
                  empty="Aucune correspondance identifiée."
                  kind="matched"
                />
                <SkillList
                  title="Compétences manquantes"
                  skills={result.missing_skills}
                  empty="Toutes les compétences obligatoires identifiées sont présentes."
                  kind="missing"
                />
              </div>
            </section>
          )}
        </div>
        <aside className="explanation">
          <span aria-hidden="true">ⓘ</span>
          <div>
            <p>
              Le score mesure la couverture des compétences obligatoires
              identifiées, pas les chances de recrutement.
            </p>
            <small>
              L’extraction peut être imparfaite. La comparaison est lexicale,
              sans synonymes ; les alternatives obligatoires ne sont pas
              représentées.
            </small>
          </div>
        </aside>
      </main>
      <footer>
        Job Copilot{" "}
        <span>
          Un éclairage sur votre candidature. La décision vous appartient.
        </span>
      </footer>
    </div>
  );
}

function SkillList({
  title,
  skills,
  empty,
  kind,
}: {
  title: string;
  skills: string[];
  empty: string;
  kind: string;
}) {
  return (
    <div className={`skill-list ${kind}`}>
      <h3>
        {title} <span>{skills.length}</span>
      </h3>
      {skills.length ? (
        <ul>
          {skills.map((skill, index) => (
            <li key={`${skill}-${index}`}>{skill}</li>
          ))}
        </ul>
      ) : (
        <p>{empty}</p>
      )}
    </div>
  );
}
