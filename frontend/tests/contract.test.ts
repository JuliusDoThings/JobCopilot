import { describe, expect, it } from "vitest";
import { isAnalyzeResult, parseInput } from "@/lib/analyze";

const input = { cv_text: " CV fictif ", job_text: " Annonce fictive " };
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

describe("input", () => {
  it("trims and validates both documents", () => {
    expect(parseInput(input)).toEqual({
      cv_text: "CV fictif",
      job_text: "Annonce fictive",
    });
  });
  for (const field of ["cv_text", "job_text"]) {
    it.each(["", " \n\t ", null, false, 12, [], {}, "x".repeat(20_001)])(
      `rejects invalid ${field}: %j`,
      (value) => {
        expect(parseInput({ ...input, [field]: value })).toBeNull();
      },
    );
    it(`validates ${field} length after trim in Unicode code points`, () => {
      expect(
        parseInput({ ...input, [field]: " " + "😀".repeat(20_000) + " " }),
      ).not.toBeNull();
    });
  }
  it.each([null, [], {}, { cv_text: "x" }, { ...input, extra: true }])(
    "rejects incorrect shapes",
    (value) => {
      expect(parseInput(value)).toBeNull();
    },
  );
});

describe("response union", () => {
  it.each([scored, { ...scored, score: 0 }, unscored])(
    "accepts valid states",
    (value) => {
      expect(isAnalyzeResult(value)).toBe(true);
    },
  );
  it.each([
    { ...scored, score: null },
    { ...scored, score: "50" },
    { ...scored, score: NaN },
    { ...scored, score: Infinity },
    { ...scored, score: -1 },
    { ...scored, score: 101 },
    { ...scored, reason: "unknown" },
    { ...scored, extra: true },
    { ...scored, matched_skills: [12] },
    { ...scored, status: "unknown" },
    { ...unscored, score: 0 },
    { ...unscored, reason: null },
    { ...unscored, matched_skills: ["python"] },
    { ...unscored, missing_skills: ["sql"] },
    null,
    {},
  ])("rejects inconsistent states", (value) => {
    expect(isAnalyzeResult(value)).toBe(false);
  });
});
