"""Offline evaluation of fictional job predictions. Never creates an Azure client."""

import argparse
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from job_copilot_api.evaluation_metrics import score_skills
from job_copilot_api.jobs.schemas import JobExtractRequest, JobRequirements

CASES_PATH = Path(__file__).resolve().parents[1] / "evaluation/fictional_jobs.json"


class JobCase(JobExtractRequest):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    expected_required_skills: list[str]

    @model_validator(mode="after")
    def validate_skills(self) -> "JobCase":
        if any(not skill.strip() for skill in self.expected_required_skills):
            raise ValueError("Blank expected skill")
        return self


class Prediction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    # null explicitly represents a technical failure, not an empty extraction.
    requirements: JobRequirements | None


def load_cases(path: Path) -> list[JobCase]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or len(raw) != 8:
        raise ValueError("Expected eight fictional jobs")
    cases = [JobCase.model_validate(case) for case in raw]
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("Duplicate case identifiers")
    return cases


def evaluate(cases: list[JobCase], predictions: list[Prediction]) -> dict:
    by_id = {prediction.id: prediction.requirements for prediction in predictions}
    if len(by_id) != len(predictions) or set(by_id) != {case.id for case in cases}:
        raise ValueError("Predictions must cover each case exactly once")
    results = []
    for case in cases:
        profile = by_id[case.id]
        scores = (
            None
            if profile is None
            else score_skills(profile.required_skills, case.expected_required_skills)
        )
        # Do not report raw documents or provider outputs. Redact document echoes.
        if scores is not None:
            for key in ("false_positives", "false_negatives"):
                scores[key] = [
                    value.replace(case.job_text.strip().casefold(), "[redacted]")
                    for value in scores[key]
                ]
        results.append(
            {
                "id": case.id,
                "status": "technical_failure" if profile is None else "success",
                "skills": scores,
            }
        )
    successes = [case for case in results if case["skills"] is not None]
    return {
        "cases": results,
        "summary": {
            "total": len(cases),
            "succeeded": len(successes),
            "failed": len(cases) - len(successes),
            "macro": {
                metric: sum(case["skills"][metric] for case in successes)
                / len(successes)
                for metric in ("precision", "recall", "f1")
            }
            if successes
            else None,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    args = parser.parse_args()
    try:
        cases = load_cases(CASES_PATH)
        raw = json.loads(args.predictions.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("Expected prediction list")
        report = evaluate(cases, [Prediction.model_validate(item) for item in raw])
    except (OSError, ValueError):
        print("Invalid or unreadable corpus or predictions.")
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(report["summary"]["failed"] != 0)


if __name__ == "__main__":
    raise SystemExit(main())
