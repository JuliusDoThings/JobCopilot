from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError

from job_copilot_api.cv import errors as cv_errors
from job_copilot_api.cv.schemas import CVProfile
from job_copilot_api.cv.service import get_cv_extractor
from job_copilot_api.jobs import errors as job_errors
from job_copilot_api.jobs.schemas import JobRequirements
from job_copilot_api.jobs.service import get_job_extractor
from job_copilot_api.main import app
from job_copilot_api.matching.schemas import MatchingAnalyzeResponse
from job_copilot_api.matching.service import match_skills

URL = "/api/v1/matching/analyze"
PAYLOAD = {
    "cv_text": "CV fictif confidentiel",
    "job_text": "Annonce fictive confidentielle",
}


@pytest.fixture
def client():
    previous = app.dependency_overrides.copy()
    app.dependency_overrides.clear()
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest.fixture
def extractors(client):
    cv = Mock()
    cv.extract.return_value = CVProfile(
        skills=[" Python ", "Git"], experiences=[], education=[]
    )
    job = Mock()
    job.extract.return_value = JobRequirements(required_skills=["PYTHON", "SQL"])
    app.dependency_overrides[get_cv_extractor] = lambda: cv
    app.dependency_overrides[get_job_extractor] = lambda: job
    return cv, job


@pytest.mark.parametrize(
    "candidate,required,score,matched,missing",
    [
        (
            ["python", "SQL", "extra"],
            [" PYTHON ", "SQL", "sql"],
            100.0,
            ["python", "sql"],
            [],
        ),
        (["Python"], ["Python", "SQL"], 50.0, ["python"], ["sql"]),
        (["Git"], ["Python"], 0.0, [], ["python"]),
        ([], ["Python"], 0.0, [], ["python"]),
        (
            ["Python", "SQL"],
            ["Python", "SQL", "Git"],
            200 / 3,
            ["python", "sql"],
            ["git"],
        ),
    ],
)
def test_scored_reuses_existing_matching(
    client, extractors, monkeypatch, candidate, required, score, matched, missing
):
    cv, job = extractors
    cv.extract.return_value = CVProfile(skills=candidate, experiences=[], education=[])
    job.extract.return_value = JobRequirements(required_skills=required)
    spy = Mock(wraps=match_skills)
    monkeypatch.setattr("job_copilot_api.matching.analysis.match_skills", spy)
    response = client.post(
        URL, json={key: " \n" + value + "\t " for key, value in PAYLOAD.items()}
    )
    assert response.status_code == 200
    result = response.json()
    assert result == {
        "status": "scored",
        "score": pytest.approx(score),
        "matched_skills": matched,
        "missing_skills": missing,
        "reason": None,
    }
    spy.assert_called_once_with(candidate, required)
    cv.extract.assert_called_once_with(PAYLOAD["cv_text"])
    job.extract.assert_called_once_with(PAYLOAD["job_text"])


@pytest.mark.parametrize("required", [[], ["", " \n\t "]])
def test_not_scorable(client, extractors, monkeypatch, required):
    cv, job = extractors
    job.extract.return_value = JobRequirements(required_skills=required)
    spy = Mock(side_effect=AssertionError("No matching for empty requirements"))
    monkeypatch.setattr("job_copilot_api.matching.analysis.match_skills", spy)
    response = client.post(URL, json=PAYLOAD)
    assert response.status_code == 200
    assert response.json() == {
        "status": "not_scorable",
        "score": None,
        "matched_skills": [],
        "missing_skills": [],
        "reason": "no_explicit_required_skills",
    }
    cv.extract.assert_called_once()
    spy.assert_not_called()


@pytest.mark.parametrize("stage", ["cv", "job"])
@pytest.mark.parametrize(
    "name,code",
    [
        ("ExtractionTimeoutError", 504),
        ("ProviderUnavailableError", 503),
        ("InvalidExtractionError", 502),
        ("ExtractionRefusedError", 502),
        ("ExtractionError", 502),
        ("ExtractionNotConfiguredError", 503),
    ],
)
def test_extraction_failure_has_no_score(
    client, extractors, monkeypatch, caplog, stage, name, code
):
    cv, job = extractors
    module = cv_errors if stage == "cv" else job_errors
    error = getattr(module, name)()
    error.args = ("RAW-PROVIDER-SECRET " + str(PAYLOAD),)
    (cv if stage == "cv" else job).extract.side_effect = error
    spy = Mock(side_effect=AssertionError("No matching after extraction failure"))
    monkeypatch.setattr("job_copilot_api.matching.analysis.match_skills", spy)
    response = client.post(URL, json=PAYLOAD)
    assert response.status_code == code
    assert response.json() == {"detail": error.public_message}
    for sensitive in [*PAYLOAD.values(), "RAW-PROVIDER-SECRET"]:
        assert sensitive not in response.text + caplog.text
    spy.assert_not_called()
    if stage == "cv":
        job.extract.assert_not_called()


@pytest.mark.parametrize("field", ["cv_text", "job_text"])
@pytest.mark.parametrize("value", ["", " \n\t ", "x" * 20_001, None, 1, True, [], {}])
def test_invalid_inputs(client, extractors, field, value):
    payload = {**PAYLOAD, field: value}
    assert client.post(URL, json=payload).status_code == 422
    for extractor in extractors:
        extractor.extract.assert_not_called()


@pytest.mark.parametrize(
    "payload", [{}, {"cv_text": "x"}, {"job_text": "x"}, {**PAYLOAD, "extra": True}]
)
def test_missing_or_extra_fields(client, extractors, payload):
    assert client.post(URL, json=payload).status_code == 422
    for extractor in extractors:
        extractor.extract.assert_not_called()


@pytest.mark.parametrize("size", [1, 20_000])
def test_text_boundaries(client, extractors, size):
    response = client.post(
        URL,
        json={"cv_text": " " + "x" * size + " ", "job_text": "\n" + "y" * size + "\t"},
    )
    assert response.status_code == 200
    extractors[0].extract.assert_called_once_with("x" * size)
    extractors[1].extract.assert_called_once_with("y" * size)


def test_strict_response_states():
    adapter = TypeAdapter(MatchingAnalyzeResponse)
    scored = {
        "status": "scored",
        "score": 50.0,
        "matched_skills": ["python"],
        "missing_skills": ["sql"],
        "reason": None,
    }
    unscored = {
        "status": "not_scorable",
        "score": None,
        "matched_skills": [],
        "missing_skills": [],
        "reason": "no_explicit_required_skills",
    }
    for valid in [scored, unscored]:
        assert adapter.validate_python(valid).model_dump() == valid
    for invalid in [
        {**scored, "score": None},
        {**scored, "score": -1},
        {**scored, "score": 101},
        {**scored, "score": "50"},
        {**scored, "reason": "no_explicit_required_skills"},
        {**scored, "matched_skills": [123]},
        {**scored, "extra": True},
        {**unscored, "score": 0.0},
        {**unscored, "reason": None},
        {**unscored, "matched_skills": ["python"]},
        {**unscored, "missing_skills": ["python"]},
        {**scored, "status": "unknown"},
    ]:
        with pytest.raises(ValidationError):
            adapter.validate_python(invalid)


def test_openapi(client):
    spec = client.get("/openapi.json").json()
    responses = spec["paths"][URL]["post"]["responses"]
    assert set(responses) == {"200", "422", "502", "503", "504"}
    schema = responses["200"]["content"]["application/json"]["schema"]
    assert schema["discriminator"]["propertyName"] == "status"
    assert len(schema["oneOf"]) == 2
    request = spec["components"]["schemas"]["MatchingAnalyzeRequest"]
    assert request["additionalProperties"] is False
    assert set(request["required"]) == {"cv_text", "job_text"}
    for name in request["required"]:
        assert request["properties"][name]["minLength"] == 1
        assert request["properties"][name]["maxLength"] == 20_000


@pytest.mark.parametrize("failure", [None, "cv", "job"])
def test_real_dependencies_close_both_clients(client, monkeypatch, failure):
    from job_copilot_api.cv.azure import AzureCVExtractor
    from job_copilot_api.jobs.azure import AzureJobExtractor

    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://fictional.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "fictional-secret")
    closed = []
    calls = []

    class FakeClient:
        def __init__(self, name):
            self.name = name

        def __enter__(self):
            return self

        def __exit__(self, *args):
            closed.append(self.name)

    monkeypatch.setattr(
        "job_copilot_api.cv.service.create_azure_client", lambda _: FakeClient("cv")
    )
    monkeypatch.setattr(
        "job_copilot_api.jobs.service.create_azure_client", lambda _: FakeClient("job")
    )

    def extract_cv(self, text):
        calls.append("cv")
        if failure == "cv":
            raise cv_errors.ExtractionTimeoutError()
        return CVProfile(skills=["Python"], experiences=[], education=[])

    def extract_job(self, text):
        calls.append("job")
        if failure == "job":
            raise job_errors.InvalidExtractionError()
        return JobRequirements(required_skills=["Python"])

    monkeypatch.setattr(AzureCVExtractor, "extract", extract_cv)
    monkeypatch.setattr(AzureJobExtractor, "extract", extract_job)
    response = client.post(URL, json=PAYLOAD)
    assert response.status_code == {None: 200, "cv": 504, "job": 502}[failure]
    assert sorted(closed) == ["cv", "job"]
    assert calls == (["cv"] if failure == "cv" else ["cv", "job"])


def test_unconfigured(client):
    response = client.post(URL, json=PAYLOAD)
    assert response.status_code == 503
    assert response.json() == {
        "detail": cv_errors.ExtractionNotConfiguredError.public_message
    }
