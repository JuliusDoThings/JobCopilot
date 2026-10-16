"""Evaluate fictional jobs offline or through explicitly authorized Azure requests."""

import argparse
import json
from pathlib import Path

from openai import APIError
from pydantic import BaseModel, ConfigDict, Field, model_validator

from job_copilot_api.azure_client import create_azure_client
from job_copilot_api.config import AzureSettings
from job_copilot_api.evaluation_metrics import score_skills
from job_copilot_api.jobs.azure import AzureJobExtractor
from job_copilot_api.jobs.errors import ExtractionError
from job_copilot_api.jobs.schemas import JobExtractRequest, JobRequirements
from job_copilot_api.jobs.service import JobExtractor

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


def extract_predictions(
    cases: list[JobCase], extractor: JobExtractor
) -> list[Prediction]:
    predictions = []
    for case in cases:
        try:
            requirements = extractor.extract(case.job_text)
        except ExtractionError:
            # Never turn a provider failure into an empty successful extraction.
            requirements = None
        predictions.append(Prediction(id=case.id, requirements=requirements))
    return predictions


def redact_report(value: object, forbidden: list[str]) -> object:
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--predictions", type=Path)
    modes.add_argument("--allow-paid-requests", action="store_true")
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args(argv)
    try:
        cases = load_cases(CASES_PATH)
        if args.json_output and args.json_output.resolve() in {
            CASES_PATH.resolve(),
            *([args.predictions.resolve()] if args.predictions else []),
        }:
            print("JSON output must not overwrite the corpus or predictions.")
            return 1
    except (OSError, ValueError):
        print("Invalid or unreadable corpus or predictions.")
        return 1
    forbidden = [case.job_text.strip().casefold() for case in cases]
    if args.predictions is not None:
        try:
            raw = json.loads(args.predictions.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                raise ValueError("Expected prediction list")
            report = evaluate(cases, [Prediction.model_validate(item) for item in raw])
        except (OSError, ValueError):
            print("Invalid or unreadable corpus or predictions.")
            return 1
    else:
        settings = AzureSettings.from_environment()
        if settings is None:
            print("Azure configuration is missing or invalid; no request was sent.")
            return 1
        for value in (
            settings.api_key,
            settings.endpoint,
            settings.base_url,
            settings.deployment,
        ):
            forbidden.extend([value, value.strip().casefold()])
        try:
            with create_azure_client(settings) as client:
                extractor = AzureJobExtractor(client, settings.deployment)
                predictions = extract_predictions(cases, extractor)
            report = evaluate(cases, predictions)
        except (APIError, ExtractionError, OSError):
            print("Evaluation client failed; no complete report is available.")
            return 1
    report = redact_report(report, forbidden)
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(output, end="")
    if args.json_output:
        try:
            args.json_output.write_text(output, encoding="utf-8")
        except OSError:
            print("Could not write JSON report.")
            return 1
    return int(report["summary"]["failed"] != 0)


if __name__ == "__main__":
    raise SystemExit(main())
