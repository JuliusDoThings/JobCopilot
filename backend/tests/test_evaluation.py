import json
import runpy
import sys
from pathlib import Path

import pytest

from job_copilot_api.config import AzureSettings
from job_copilot_api.cv.schemas import CVExtractRequest

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
