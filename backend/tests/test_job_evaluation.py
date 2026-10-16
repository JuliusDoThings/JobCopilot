import json
import runpy
import sys
from pathlib import Path

import pytest

from job_copilot_api.evaluation_metrics import score_skills
from job_copilot_api.jobs.schemas import JobRequirements

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def evaluation():
    return runpy.run_path(str(BACKEND / "scripts/evaluate_job_extraction.py"))


def test_fictional_jobs_and_offline_cli(evaluation, tmp_path, monkeypatch, capsys):
    cases = evaluation["load_cases"](BACKEND / "evaluation/fictional_jobs.json")
    assert len(cases) == 8
    assert all("fictive" in case.job_text for case in cases)
    by_id = {case.id: case.expected_required_skills for case in cases}
    assert by_id["preferred"] == ["Python"]
    assert by_id["context"] == ["Excel"]
    assert by_id["none"] == by_id["ambiguous"] == []
    assert by_id["alternative"] == ["Docker"]
    assert by_id["untrusted"] == ["SQL"]
    predictions = [
        {
            "id": case.id,
            "requirements": {
                "required_skills": case.expected_required_skills,
            },
        }
        for case in cases
    ]
    path = tmp_path / "predictions.json"
    path.write_text(json.dumps(predictions))
    monkeypatch.setattr(sys, "argv", ["evaluate", "--predictions", str(path)])
    assert evaluation["main"]() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["summary"]["macro"] == dict(precision=1, recall=1, f1=1)
    assert report["summary"]["succeeded"] == 8
    assert all(case.job_text not in json.dumps(report) for case in cases)


@pytest.mark.parametrize("failed", [False, True])
def test_technical_failure_separated_from_quality(evaluation, failed):
    cases = evaluation["load_cases"](BACKEND / "evaluation/fictional_jobs.json")
    predictions = [
        evaluation["Prediction"](
            id=case.id,
            requirements=None if failed else JobRequirements(required_skills=[]),
        )
        for case in cases
    ]
    report = evaluation["evaluate"](cases, predictions)
    assert report["summary"]["failed"] == (8 if failed else 0)
    if failed:
        assert report["summary"]["macro"] is None
    else:
        assert report["summary"]["macro"]["recall"] < 1


@pytest.mark.parametrize("damage", ["duplicate", "count", "blank", "type"])
def test_invalid_corpus(evaluation, tmp_path, damage):
    raw = json.loads((BACKEND / "evaluation/fictional_jobs.json").read_text())
    if damage == "duplicate":
        raw[-1]["id"] = raw[0]["id"]
    elif damage == "count":
        raw.pop()
    elif damage == "blank":
        raw[-1]["expected_required_skills"] = [" "]
    else:
        raw[-1]["job_text"] = 1
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        evaluation["load_cases"](path)


def test_prediction_coverage_and_invalid_cli(evaluation, tmp_path, monkeypatch, capsys):
    cases = evaluation["load_cases"](BACKEND / "evaluation/fictional_jobs.json")
    with pytest.raises(ValueError):
        evaluation["evaluate"](cases, [])
    repeated = [evaluation["Prediction"](id=cases[0].id, requirements=None)] * 8
    with pytest.raises(ValueError):
        evaluation["evaluate"](cases, repeated)
    path = tmp_path / "bad.json"
    path.write_text('{"provider_secret": "do-not-print"}')
    monkeypatch.setattr(sys, "argv", ["evaluate", "--predictions", str(path)])
    assert evaluation["main"]() == 1
    assert "do-not-print" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "actual,expected,p,r,f1",
    [
        ([], [], 1, 1, 1),
        ([], ["Python"], 0, 0, 0),
        (["Python"], [], 0, 1, 0),
        ([" Python ", "python", "Git"], ["PYTHON"], 0.5, 1, 2 / 3),
    ],
)
def test_shared_metrics_preserve_conventions(actual, expected, p, r, f1):
    scores = score_skills(actual, expected)
    assert scores["precision"] == p
    assert scores["recall"] == r
    assert scores["f1"] == pytest.approx(f1)
