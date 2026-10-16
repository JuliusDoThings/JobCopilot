export const MAX_TEXT_LENGTH = 20_000;

export type AnalyzeInput = { cv_text: string; job_text: string };
export type AnalyzeResult =
  | {
      status: "scored";
      score: number;
      matched_skills: string[];
      missing_skills: string[];
      reason: null;
    }
  | {
      status: "not_scorable";
      score: null;
      matched_skills: [];
      missing_skills: [];
      reason: "no_explicit_required_skills";
    };

export function textLength(value: string): number {
  return Array.from(value.trim()).length;
}

export function fieldError(value: string, label: string): string | null {
  if (!value.trim()) return `${label} est obligatoire.`;
  if (textLength(value) > MAX_TEXT_LENGTH)
    return `${label} doit contenir au maximum 20 000 caractères après suppression des espaces aux extrémités.`;
  return null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function parseInput(value: unknown): AnalyzeInput | null {
  if (!isRecord(value) || Object.keys(value).length !== 2) return null;
  if (typeof value.cv_text !== "string" || typeof value.job_text !== "string")
    return null;
  if (
    fieldError(value.cv_text, "Le CV") ||
    fieldError(value.job_text, "L’offre")
  )
    return null;
  return { cv_text: value.cv_text.trim(), job_text: value.job_text.trim() };
}

export function isAnalyzeResult(value: unknown): value is AnalyzeResult {
  if (!isRecord(value) || Object.keys(value).length !== 5) return false;
  if (
    !Array.isArray(value.matched_skills) ||
    !Array.isArray(value.missing_skills)
  )
    return false;
  if (
    ![...value.matched_skills, ...value.missing_skills].every(
      (s) => typeof s === "string",
    )
  )
    return false;
  if (value.status === "scored") {
    return (
      typeof value.score === "number" &&
      Number.isFinite(value.score) &&
      value.score >= 0 &&
      value.score <= 100 &&
      value.reason === null
    );
  }
  return (
    value.status === "not_scorable" &&
    value.score === null &&
    value.matched_skills.length === 0 &&
    value.missing_skills.length === 0 &&
    value.reason === "no_explicit_required_skills"
  );
}

export function errorMessage(status: number): string {
  switch (status) {
    case 422:
      return "Les textes n’ont pas pu être analysés. Vérifiez leur contenu et leur longueur.";
    case 503:
      return "Le service d’analyse est indisponible. Réessayez plus tard.";
    case 504:
      return "L’analyse a pris trop de temps. Vous pouvez réessayer plus tard.";
    default:
      return "L’analyse n’a pas abouti. Réessayez plus tard.";
  }
}
