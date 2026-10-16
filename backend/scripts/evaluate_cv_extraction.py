"""Opt-in paid evaluation using exclusively the bundled fictional CVs."""

import argparse
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from job_copilot_api.config import AzureSettings
from job_copilot_api.cv.azure import AzureCVExtractor, create_azure_client
from job_copilot_api.cv.errors import ExtractionError
from job_copilot_api.cv.schemas import CVExtractRequest
from job_copilot_api.cv.service import CVExtractor
from job_copilot_api.evaluation_metrics import normalize, score_skills

CASES_PATH = Path(__file__).resolve().parents[1] / "evaluation/fictional_cvs.json"


class ListExpectation(BaseModel):
    """Evaluation metadata only; fragments in each group must share one item."""

    model_config = ConfigDict(extra="forbid", strict=True)
    min_items: int = Field(ge=0)
    max_items: int = Field(ge=0)
    fragment_groups: list[list[str]]

    @model_validator(mode="after")
    def consistent(self) -> "ListExpectation":
        if self.min_items > self.max_items:
            raise ValueError("Invalid cardinality interval")
        if any(
            not group or any(not s.strip() for s in group)
            for group in self.fragment_groups
        ):
            raise ValueError("Empty fragment group or fragment")
        if self.max_items == 0 and self.fragment_groups:
            raise ValueError("Empty list cannot contain fragments")
        return self


class EvaluationCase(CVExtractRequest):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    expected_skills: list[str]
    experiences: ListExpectation
    education: ListExpectation

    @model_validator(mode="after")
    def nonblank_skills(self) -> "EvaluationCase":
        if any(not skill.strip() for skill in self.expected_skills):
            raise ValueError("Blank expected skill")
        return self


def load_cases(path: Path) -> list[EvaluationCase]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not 10 <= len(raw) <= 15:
        raise ValueError("Expected 10 to 15 cases")
    cases = [EvaluationCase.model_validate(case) for case in raw]
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("Duplicate case identifiers")
    return cases


def check_list(items: list[str], expected: ListExpectation) -> dict:
    values = [normalize(item) for item in items]
    checks = {
        "cardinality": expected.min_items <= len(items) <= expected.max_items,
        "nonblank": all(values),
        "no_duplicates": len(values) == len(set(values)),
        "fragment_groups": [
            any(
                all(normalize(fragment) in value for fragment in group)
                for value in values
            )
            for group in expected.fragment_groups
        ],
    }
    return {
        **checks,
        "passed": all(
            [
                checks["cardinality"],
                checks["nonblank"],
                checks["no_duplicates"],
                *checks["fragment_groups"],
            ]
        ),
    }


def redact_report(value: object, forbidden: list[str]) -> object:
    """Also protect reports if a provider echoes CV text in a skill string."""
    if isinstance(value, str):
        for text in forbidden:
            if text:
                value = value.replace(text, "[redacted]")
        return value
    if isinstance(value, list):
        return [redact_report(item, forbidden) for item in value]
    if isinstance(value, dict):
        return {key: redact_report(item, forbidden) for key, item in value.items()}
    return value


def evaluate(cases: list[EvaluationCase], extractor: CVExtractor) -> dict:
    results = []
    for case in cases:
        try:
            profile = extractor.extract(case.cv_text)
        except ExtractionError as exc:
            # Fixed categories only: never serialize exception details or messages.
            results.append(
                {
                    "id": case.id,
                    "status": "technical_failure",
                    "error_category": type(exc).__name__,
                    "skills": None,
                    "experiences": None,
                    "education": None,
                }
            )
            continue
        results.append(
            {
                "id": case.id,
                "status": "success",
                "skills": score_skills(profile.skills, case.expected_skills),
                "experiences": check_list(profile.experiences, case.experiences),
                "education": check_list(profile.education, case.education),
            }
        )
    successful = [result for result in results if result["status"] == "success"]
    report = {
        "cases": results,
        "summary": {
            "total": len(cases),
            "succeeded": len(successful),
            "failed": len(cases) - len(successful),
            "macro": {
                metric: sum(r["skills"][metric] for r in successful) / len(successful)
                for metric in ("precision", "recall", "f1")
            }
            if successful
            else None,
        },
    }

    return redact_report(report, [normalize(case.cv_text) for case in cases])


def print_report(report: dict) -> None:
    for result in report["cases"]:
        if result["status"] == "technical_failure":
            print(f"{result['id']}: technical_failure ({result['error_category']})")
            continue
        scores = result["skills"]
        print(
            f"{result['id']}: "
            + ", ".join(
                f"{key}={scores[key]:.2f}" for key in ("precision", "recall", "f1")
            )
        )
        print(
            f"  FP={json.dumps(scores['false_positives'], ensure_ascii=False)}; "
            f"FN={json.dumps(scores['false_negatives'], ensure_ascii=False)}"
        )
        for field in ("experiences", "education"):
            print(f"  {field}: {json.dumps(result[field], sort_keys=True)}")
    summary = report["summary"]
    print(
        f"Technical summary: {summary['succeeded']}/{summary['total']} succeeded; "
        f"{summary['failed']} failed."
    )
    if summary["macro"] is None:
        print("Business quality: not available (no successful extraction).")
    else:
        print(
            f"Business quality (macro average over {summary['succeeded']} "
            "successful cases): "
            + ", ".join(f"{key}={value:.2f}" for key, value in summary["macro"].items())
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-paid-requests", action="store_true")
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()
    if not args.allow_paid_requests:
        parser.error("Explicit --allow-paid-requests is required; no request was sent.")
    try:
        cases = load_cases(CASES_PATH)
    except (OSError, ValueError):
        print("Evaluation corpus is invalid or unreadable; no request was sent.")
        return 1
    settings = AzureSettings.from_environment()
    if settings is None:
        print("Azure configuration is missing or invalid; no request was sent.")
        return 1
    with create_azure_client(settings) as client:
        report = evaluate(cases, AzureCVExtractor(client, settings.deployment))
    report = redact_report(report, [settings.api_key, normalize(settings.api_key)])
    print_report(report)
    if args.json_output:
        try:
            args.json_output.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            print("Could not write JSON report.")
            return 1
    return int(report["summary"]["failed"] != 0)


if __name__ == "__main__":
    raise SystemExit(main())
