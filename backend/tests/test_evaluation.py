import json
import runpy
import sys
from pathlib import Path

import pytest

from job_copilot_api.config import AzureSettings
from job_copilot_api.cv.errors import ExtractionError
from job_copilot_api.cv.schemas import CVExtractRequest, CVProfile

BACKEND = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("opt_in,exit_code", [(False, 2), (True, 1)])
def test_evaluation_guard(
    monkeypatch: pytest.MonkeyPatch, opt_in: bool, exit_code: int
) -> None:
    args = ["evaluate_cv_extraction.py"]
    if opt_in:
        args.append("--allow-paid-requests")
    monkeypatch.setattr(sys, "argv", args)
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(
            str(BACKEND / "scripts/evaluate_cv_extraction.py"), run_name="__main__"
        )
    assert exc.value.code == exit_code


def test_fictional_dataset_is_valid() -> None:
    cases = json.loads((BACKEND / "evaluation/fictional_cvs.json").read_text())
    assert len(cases) == 4
    assert len({case["id"] for case in cases}) == 4
    for case in cases:
        CVExtractRequest.model_validate({"cv_text": case["cv_text"]})
        assert "fictif" in case["cv_text"]
        assert all(isinstance(skill, str) for skill in case["expected_skills"])


def test_environment_file_is_not_loaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text(
        "AZURE_OPENAI_ENDPOINT=https://fictional.openai.azure.com\n"
        "AZURE_OPENAI_DEPLOYMENT=gpt-4.1-mini\n"
        "AZURE_OPENAI_API_KEY=fictional-key\n"
    )
    monkeypatch.chdir(tmp_path)
    assert AzureSettings.from_environment() is None


@pytest.mark.parametrize(
    "mode,exit_code,summary",
    [
        ("mixed", 1, "precision=0.50, recall=0.50"),
        ("poor", 0, "precision=0.00, recall=0.25"),
        ("failed", 1, "not available (no successful extraction)"),
    ],
)
def test_aggregate_quality_and_technical_status(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    mode: str,
    exit_code: int,
    summary: str,
) -> None:
    # Exercise the real script over four fixed fictional cases with no SDK calls.
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://fictional.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "fictional-key")
    monkeypatch.setattr(
        sys, "argv", ["evaluate_cv_extraction.py", "--allow-paid-requests"]
    )

    class FakeClient:
        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args: object) -> None:
            pass

    class FakeExtractor:
        def __init__(self, *args: object) -> None:
            self.index = 0

        def extract(self, cv_text: str) -> CVProfile:
            self.index += 1
            if mode == "failed" or (mode == "mixed" and self.index > 2):
                raise ExtractionError
            # First case has precision=recall=1; second has both 0.
            skills = (
                ["Python", "FastAPI"]
                if mode == "mixed" and self.index == 1
                else ["wrong"]
            )
            return CVProfile(skills=skills, experiences=[], education=[])

    monkeypatch.setattr(
        "job_copilot_api.cv.azure.create_azure_client", lambda settings: FakeClient()
    )
    monkeypatch.setattr("job_copilot_api.cv.azure.AzureCVExtractor", FakeExtractor)
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(
            str(BACKEND / "scripts/evaluate_cv_extraction.py"), run_name="__main__"
        )
    assert exc.value.code == exit_code
    output = capsys.readouterr().out
    assert summary in output
    successful = {"mixed": 2, "poor": 4, "failed": 0}[mode]
    assert (
        f"Technical summary: {successful}/4 succeeded; {4 - successful} failed."
        in output
    )
    if successful:
        assert f"macro average over {successful} successful cases" in output
