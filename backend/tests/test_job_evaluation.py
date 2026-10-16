import json
import runpy
import sys
from pathlib import Path

import pytest

from job_copilot_api.evaluation_metrics import score_skills
from job_copilot_api.jobs.schemas import JobRequirements

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def evaluation(monkeypatch):
    module = runpy.run_path(str(BACKEND / "scripts/evaluate_job_extraction.py"))

    def forbidden(*args, **kwargs):
        pytest.fail("An evaluation test attempted to create a real Azure client")

    monkeypatch.setitem(module["main"].__globals__, "create_azure_client", forbidden)
    return module


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


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["--json-output", "unused.json"],
        ["--predictions", "unused.json", "--allow-paid-requests"],
    ],
)
def test_mode_guard_prevents_client(evaluation, argv):
    with pytest.raises(SystemExit) as exc:
        evaluation["main"](argv)
    assert exc.value.code == 2


@pytest.mark.parametrize("damage", ["late_invalid", "duplicate", "unreadable"])
def test_paid_invalid_corpus_never_creates_client(
    evaluation, monkeypatch, tmp_path, capsys, damage
):
    path = tmp_path / "cases.json"
    if damage != "unreadable":
        raw = json.loads((BACKEND / "evaluation/fictional_jobs.json").read_text())
        if damage == "late_invalid":
            raw[-1]["job_text"] = " "
        else:
            raw[-1]["id"] = raw[0]["id"]
        path.write_text(json.dumps(raw))
    monkeypatch.setitem(evaluation["main"].__globals__, "CASES_PATH", path)
    assert evaluation["main"](["--allow-paid-requests"]) == 1
    assert "Invalid or unreadable corpus" in capsys.readouterr().out


@pytest.mark.parametrize(
    "endpoint",
    [None, "http://invalid.example", "https://[", "https://attacker.example"],
)
def test_paid_configuration_error(evaluation, monkeypatch, capsys, endpoint):
    if endpoint is not None:
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", endpoint)
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "secret-marker")
    assert evaluation["main"](["--allow-paid-requests"]) == 1
    output = capsys.readouterr().out
    assert "configuration is missing or invalid" in output
    assert "secret-marker" not in output


@pytest.fixture
def simulated_azure(evaluation, monkeypatch):
    from job_copilot_api.config import AzureSettings

    state = {"created": 0, "closed": 0, "calls": [], "mode": "perfect"}
    cases = evaluation["load_cases"](BACKEND / "evaluation/fictional_jobs.json")
    by_text = {case.job_text: case for case in cases}
    settings = AzureSettings(
        "https://fictional.openai.azure.com", "gpt-4.1-mini", "SECRET-MARKER"
    )
    monkeypatch.setattr(AzureSettings, "from_environment", lambda: settings)

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            state["closed"] += 1

    def create(settings_arg):
        assert settings_arg is settings
        state["created"] += 1
        return FakeClient()

    class FakeExtractor:
        def __init__(self, client, deployment):
            assert isinstance(client, FakeClient)
            assert deployment == settings.deployment

        def extract(self, text):
            from job_copilot_api.jobs.errors import ExtractionTimeoutError

            state["calls"].append(text)
            case = by_text[text]
            if state["mode"] == "failed" or (
                state["mode"] == "mixed" and case.id == "untrusted"
            ):
                error = ExtractionTimeoutError()
                error.args = ("provider-internal-details " + settings.api_key + text,)
                raise error
            if state["mode"] == "unexpected":
                raise RuntimeError("simulated programming failure")
            if state["mode"] == "mixed" and case.id == "explicit":
                return JobRequirements(required_skills=["Python", "unwanted"])
            if state["mode"] == "empty":
                return JobRequirements(required_skills=[])
            if state["mode"] == "echo":
                return JobRequirements(
                    required_skills=[
                        text,
                        settings.api_key,
                        settings.api_key.casefold(),
                        settings.endpoint,
                        settings.base_url,
                        settings.deployment,
                    ]
                )
            return JobRequirements(required_skills=case.expected_required_skills)

    globals_ = evaluation["main"].__globals__
    monkeypatch.setitem(globals_, "create_azure_client", create)
    monkeypatch.setitem(globals_, "AzureJobExtractor", FakeExtractor)
    return state, cases


@pytest.mark.parametrize(
    "mode,exit_code,successes",
    [
        ("perfect", 0, 8),
        ("empty", 0, 8),
        ("mixed", 1, 7),
        ("failed", 1, 0),
        ("echo", 0, 8),
    ],
)
def test_paid_mode_simulated_report(
    evaluation, simulated_azure, tmp_path, capsys, mode, exit_code, successes
):
    state, cases = simulated_azure
    state["mode"] = mode
    path = tmp_path / "report.json"
    assert (
        evaluation["main"](["--allow-paid-requests", "--json-output", str(path)])
        == exit_code
    )
    output = capsys.readouterr().out
    report = json.loads(output)
    assert report == json.loads(path.read_text())
    assert state["created"] == state["closed"] == 1
    assert state["calls"] == [case.job_text for case in cases]
    assert report["summary"]["succeeded"] == successes
    assert report["summary"]["failed"] == 8 - successes
    if mode == "perfect":
        assert report["summary"]["macro"] == dict(precision=1, recall=1, f1=1)
    if mode == "empty":
        assert report["summary"]["macro"]["recall"] == 0.25
    if mode == "mixed":
        assert report["cases"][0]["skills"]["false_positives"] == ["unwanted"]
        assert report["cases"][0]["skills"]["false_negatives"] == ["fastapi"]
        assert report["cases"][-1]["status"] == "technical_failure"
        assert report["cases"][-1]["skills"] is None
        assert report["summary"]["macro"]["f1"] == pytest.approx(6.5 / 7)
    if not successes:
        assert report["summary"]["macro"] is None
    serialized = path.read_text() + output
    for case in cases:
        assert case.job_text not in serialized
        assert case.job_text.casefold() not in serialized
    for sensitive in (
        "SECRET-MARKER",
        "secret-marker",
        "provider-internal-details",
        "fictional.openai.azure.com",
        "gpt-4.1-mini",
    ):
        assert sensitive not in serialized


def test_client_closed_on_unexpected_error(evaluation, simulated_azure):
    state, _ = simulated_azure
    state["mode"] = "unexpected"
    with pytest.raises(RuntimeError):
        evaluation["main"](["--allow-paid-requests"])
    assert state["closed"] == 1


def test_json_write_error(evaluation, simulated_azure, tmp_path, capsys):
    state, _ = simulated_azure
    assert (
        evaluation["main"](["--allow-paid-requests", "--json-output", str(tmp_path)])
        == 1
    )
    assert "Could not write JSON report" in capsys.readouterr().out
    assert state["closed"] == 1


def test_offline_export_without_configuration(evaluation, tmp_path, capsys):
    cases = evaluation["load_cases"](BACKEND / "evaluation/fictional_jobs.json")
    predictions = tmp_path / "predictions.json"
    predictions.write_text(
        json.dumps(
            [{"id": case.id, "requirements": {"required_skills": []}} for case in cases]
        )
    )
    output_path = tmp_path / "report.json"
    assert (
        evaluation["main"](
            ["--predictions", str(predictions), "--json-output", str(output_path)]
        )
        == 0
    )
    assert json.loads(output_path.read_text()) == json.loads(capsys.readouterr().out)
    assert (
        evaluation["main"](
            ["--predictions", str(predictions), "--json-output", str(predictions)]
        )
        == 1
    )


def test_export_cannot_overwrite_corpus(evaluation):
    assert (
        evaluation["main"](
            [
                "--allow-paid-requests",
                "--json-output",
                str(BACKEND / "evaluation/fictional_jobs.json"),
            ]
        )
        == 1
    )


def test_client_setup_error_is_sanitized(
    evaluation, simulated_azure, monkeypatch, capsys
):
    import httpx
    from openai import APIConnectionError

    def broken_factory(settings):
        raise APIConnectionError(
            message="provider-detail SECRET-MARKER",
            request=httpx.Request("POST", "https://fictional.openai.azure.com"),
        )

    monkeypatch.setitem(
        evaluation["main"].__globals__, "create_azure_client", broken_factory
    )
    assert evaluation["main"](["--allow-paid-requests"]) == 1
    output = capsys.readouterr().out
    assert output == "Evaluation client failed; no complete report is available.\n"
