"""Opt-in paid evaluation using exclusively the bundled fictional CVs."""

import argparse
import json
from pathlib import Path

from job_copilot_api.config import AzureSettings
from job_copilot_api.cv.azure import AzureCVExtractor, create_azure_client
from job_copilot_api.cv.errors import ExtractionError
from job_copilot_api.cv.schemas import CVExtractRequest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-paid-requests", action="store_true")
    args = parser.parse_args()
    if not args.allow_paid_requests:
        parser.error("Explicit --allow-paid-requests is required; no request was sent.")
    settings = AzureSettings.from_environment()
    if settings is None:
        print("Azure configuration is missing or invalid; no request was sent.")
        return 1
    cases_path = Path(__file__).resolve().parents[1] / "evaluation/fictional_cvs.json"
    cases = json.loads(cases_path.read_text())
    successes = 0
    precision_sum = recall_sum = 0.0
    with create_azure_client(settings) as client:
        extractor = AzureCVExtractor(client, settings.deployment)
        for case in cases:
            request = CVExtractRequest(cv_text=case["cv_text"])
            try:
                profile = extractor.extract(request.cv_text)
            except ExtractionError as exc:
                print(f"{case['id']}: {exc.public_message}")
                continue
            actual = {skill.strip().casefold() for skill in profile.skills}
            expected = {skill.casefold() for skill in case["expected_skills"]}
            true_positives = len(actual & expected)
            precision = true_positives / len(actual) if actual else float(not expected)
            recall = true_positives / len(expected) if expected else 1.0
            successes += 1
            precision_sum += precision
            recall_sum += recall
            print(f"{case['id']}: precision={precision:.2f}, recall={recall:.2f}")
    print(
        f"Technical summary: {successes}/{len(cases)} succeeded; "
        f"{len(cases) - successes} failed."
    )
    if successes:
        print(
            f"Business quality (macro average over {successes} successful cases): "
            f"precision={precision_sum / successes:.2f}, "
            f"recall={recall_sum / successes:.2f}"
        )
    else:
        print("Business quality: not available (no successful extraction).")
    return int(successes != len(cases))


if __name__ == "__main__":
    raise SystemExit(main())
