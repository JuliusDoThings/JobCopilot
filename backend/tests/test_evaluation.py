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
    assert len(cases) == 12
    assert len({case["id"] for case in cases}) == 12
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
        ("poor", 0, "precision=0.00, recall=0.08"),
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
    # Exercise the real script over twelve fixed fictional cases with no SDK calls.
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
    successful = {"mixed": 2, "poor": 12, "failed": 0}[mode]
    assert (
        f"Technical summary: {successful}/12 succeeded; {12 - successful} failed."
        in output
    )
    if successful:
        assert f"macro average over {successful} successful cases" in output


@pytest.fixture
def evaluation() -> dict:
    return runpy.run_path(str(BACKEND / "scripts/evaluate_cv_extraction.py"))


@pytest.mark.parametrize(
    "actual,expected,precision,recall,f1,fp,fn",
    [
        ([], [], 1, 1, 1, [], []),
        ([], ["Python"], 0, 0, 0, [], ["python"]),
        (["Python"], [], 0, 1, 0, ["python"], []),
        (["Python"], ["Python"], 1, 1, 1, [], []),
        (["SQL"], ["Python"], 0, 0, 0, ["sql"], ["python"]),
        (["Python", "SQL"], ["Python"], 0.5, 1, 2 / 3, ["sql"], []),
        ([" PYTHON ", "python"], [" Python "], 1, 1, 1, [], []),
        (["C", "C++"], ["C#", "C++"], 0.5, 0.5, 0.5, ["c"], ["c#"]),
    ],
)
def test_skill_metrics(evaluation, actual, expected, precision, recall, f1, fp, fn):
    result = evaluation["score_skills"](actual, expected)
    assert result["precision"] == precision
    assert result["recall"] == recall
    assert result["f1"] == pytest.approx(f1)
    assert result["false_positives"] == fp
    assert result["false_negatives"] == fn
    assert result["true_positives"] == len(
        {s.strip().casefold() for s in actual}
        & {s.strip().casefold() for s in expected}
    )


@pytest.mark.parametrize(
    "items,minimum,maximum,groups,passed",
    [
        ([], 0, 0, [], True),
        (["x"], 0, 0, [], False),
        ([], 1, 2, [], False),
        ([" "], 1, 2, [], False),
        (["X", " x "], 1, 2, [], False),
        ([" Atlas 2024 "], 1, 2, [["atlas", "2024"]], True),
        (["Atlas", "2024"], 1, 2, [["Atlas", "2024"]], False),
        (["Atlas 2023"], 1, 2, [["Atlas", "2024"]], False),
    ],
)
def test_list_checks(evaluation, items, minimum, maximum, groups, passed):
    expectation = evaluation["ListExpectation"](
        min_items=minimum, max_items=maximum, fragment_groups=groups
    )
    assert evaluation["check_list"](items, expectation)["passed"] is passed


@pytest.mark.parametrize(
    "damage",
    [
        "late_invalid",
        "duplicate",
        "count",
        "interval",
        "blank_fragment",
        "empty_group",
        "blank_skill",
    ],
)
def test_invalid_corpus_prevents_client_creation(
    evaluation, tmp_path, monkeypatch, capsys, damage
):
    cases = json.loads((BACKEND / "evaluation/fictional_cvs.json").read_text())
    if damage == "late_invalid":
        cases[-1]["cv_text"] = " "
    elif damage == "duplicate":
        cases[-1]["id"] = cases[0]["id"]
    elif damage == "count":
        cases = cases[:4]
    elif damage == "interval":
        cases[-1]["education"]["max_items"] = 0
    elif damage == "blank_fragment":
        cases[-1]["education"]["fragment_groups"] = [[" "]]
    elif damage == "empty_group":
        cases[-1]["education"]["fragment_groups"] = [[]]
    else:
        cases[-1]["expected_skills"] = [" "]
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(cases))
    globals_ = evaluation["main"].__globals__
    monkeypatch.setitem(globals_, "CASES_PATH", path)

    def forbidden(*args):
        pytest.fail("Client must not be created")

    monkeypatch.setitem(globals_, "create_azure_client", forbidden)
    monkeypatch.setattr(sys, "argv", ["evaluate", "--allow-paid-requests"])
    assert evaluation["main"]() == 1
    assert "corpus is invalid" in capsys.readouterr().out


def test_guard_with_valid_configuration(evaluation, monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://fictional.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "fictional")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "fictional")
    monkeypatch.setattr(sys, "argv", ["evaluate"])

    def forbidden(*args):
        pytest.fail("Guard must prevent client creation")

    monkeypatch.setitem(
        evaluation["main"].__globals__, "create_azure_client", forbidden
    )
    with pytest.raises(SystemExit) as exc:
        evaluation["main"]()
    assert exc.value.code == 2


def test_report_and_json_export(evaluation, monkeypatch, tmp_path, capsys):
    cases = evaluation["load_cases"](BACKEND / "evaluation/fictional_cvs.json")
    assert len(cases) == 12

    class FakeExtractor:
        def extract(self, text):
            if text == cases[2].cv_text:
                raise ExtractionError()
            # Unequal P and R verify mean(F1), rather than F1(mean(P), mean(R)).
            return CVProfile(skills=["Python"], experiences=[], education=[])

    report = evaluation["evaluate"](cases, FakeExtractor())
    success = [c for c in report["cases"] if c["status"] == "success"]
    assert report["summary"]["macro"]["f1"] == pytest.approx(
        sum(c["skills"]["f1"] for c in success) / 11
    )
    assert report["cases"][2]["skills"] is None
    assert report["summary"]["failed"] == 1

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    globals_ = evaluation["main"].__globals__
    monkeypatch.setitem(globals_, "create_azure_client", lambda _: FakeClient())
    monkeypatch.setitem(globals_, "AzureCVExtractor", lambda *args: FakeExtractor())
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://fictional.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "fictional")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "secret-test-marker")
    path = tmp_path / "report.json"
    monkeypatch.setattr(
        sys, "argv", ["evaluate", "--allow-paid-requests", "--json-output", str(path)]
    )
    assert evaluation["main"]() == 1
    assert json.loads(path.read_text()) == report
    output = capsys.readouterr().out
    assert "FP=" in output and "FN=" in output
    assert "11/12 succeeded; 1 failed" in output
    serialized = output + path.read_text()
    assert "secret-test-marker" not in serialized
    for case in cases:
        assert case.cv_text not in serialized
    assert all("error_category" not in c for c in success)


def test_failure_report_excludes_exception_details(evaluation, capsys):
    cases = evaluation["load_cases"](BACKEND / "evaluation/fictional_cvs.json")

    class BrokenExtractor:
        def extract(self, text):
            error = ExtractionError()
            error.args = ("provider-internal-secret " + text,)
            raise error

    report = evaluation["evaluate"](cases, BrokenExtractor())
    evaluation["print_report"](report)
    assert report["summary"]["macro"] is None
    assert report["summary"]["failed"] == 12
    serialized = json.dumps(report) + capsys.readouterr().out
    assert "provider-internal-secret" not in serialized
    assert all(case.cv_text not in serialized for case in cases)
    assert {r["error_category"] for r in report["cases"]} == {"ExtractionError"}


def test_provider_echo_is_redacted(evaluation):
    cases = evaluation["load_cases"](BACKEND / "evaluation/fictional_cvs.json")

    class EchoExtractor:
        def extract(self, text):
            return CVProfile(skills=[text], experiences=[text], education=[text])

    report = evaluation["evaluate"](cases, EchoExtractor())
    serialized = json.dumps(report, ensure_ascii=False)
    assert "[redacted]" in serialized
    for case in cases:
        assert case.cv_text.casefold() not in serialized
    assert evaluation["redact_report"](
        {"skills": ["secret-key", "SECRET-KEY"]}, ["secret-key", "SECRET-KEY"]
    ) == {"skills": ["[redacted]", "[redacted]"]}
