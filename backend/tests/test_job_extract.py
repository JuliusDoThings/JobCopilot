from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from job_copilot_api.jobs.schemas import JobRequirements
from job_copilot_api.jobs.service import get_job_extractor
from job_copilot_api.main import app

PROFILE = JobRequirements(required_skills=["Python"])


class FakeExtractor:
    def __init__(self, profile: JobRequirements = PROFILE) -> None:
        self.profile = profile
        self.received_texts: list[str] = []

    def extract(self, job_text: str) -> JobRequirements:
        self.received_texts.append(job_text)
        return self.profile


@pytest.fixture
def client() -> Iterator[TestClient]:
    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides.clear()
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest.fixture
def fake_extractor(client: TestClient) -> FakeExtractor:
    fake = FakeExtractor()
    app.dependency_overrides[get_job_extractor] = lambda: fake
    return fake


def test_extract_valid_job(client: TestClient, fake_extractor: FakeExtractor) -> None:
    response = client.post(
        "/api/v1/jobs/extract",
        json={"job_text": " \n Annonce entièrement fictive. \t "},
    )

    assert response.status_code == 200
    assert response.json() == PROFILE.model_dump()
    assert fake_extractor.received_texts == ["Annonce entièrement fictive."]


@pytest.mark.parametrize(
    "payload",
    [
        {"job_text": ""},
        {"job_text": "   \n\t "},
        {"job_text": "x" * 20_001},
        {"job_text": " \n" + "x" * 20_001 + "\t "},
        {"job_text": None},
        {"job_text": 123},
        {},
    ],
    ids=[
        "empty",
        "whitespace",
        "too-long",
        "trimmed-too-long",
        "null",
        "number",
        "missing",
    ],
)
def test_invalid_input(
    client: TestClient, fake_extractor: FakeExtractor, payload: dict[str, object]
) -> None:
    response = client.post("/api/v1/jobs/extract", json=payload)

    assert response.status_code == 422
    assert fake_extractor.received_texts == []


@pytest.mark.parametrize("padding", ["", " \n\t "])
def test_maximum_length_after_strip(
    client: TestClient, fake_extractor: FakeExtractor, padding: str
) -> None:
    response = client.post(
        "/api/v1/jobs/extract", json={"job_text": padding + "x" * 20_000 + padding}
    )

    assert response.status_code == 200
    assert response.json() == PROFILE.model_dump()
    assert fake_extractor.received_texts == ["x" * 20_000]


def test_empty_profile_lists(client: TestClient, fake_extractor: FakeExtractor) -> None:
    fake_extractor.profile = JobRequirements(required_skills=[])

    response = client.post("/api/v1/jobs/extract", json={"job_text": "Offre fictive."})

    assert response.status_code == 200
    assert response.json() == {"required_skills": []}


@pytest.mark.parametrize("missing_field", ["required_skills"])
def test_profile_fields_are_required(missing_field: str) -> None:
    data = PROFILE.model_dump()
    del data[missing_field]

    with pytest.raises(ValidationError):
        JobRequirements.model_validate(data)


def test_unconfigured_provider(client: TestClient) -> None:
    response = client.post("/api/v1/jobs/extract", json={"job_text": "Offre fictive."})

    assert response.status_code == 503
    assert response.json() == {"detail": "Job extraction service is not configured."}


def test_openapi_exposes_extraction(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    operation = response.json()["paths"]["/api/v1/jobs/extract"]["post"]
    assert set(operation["responses"]) == {"200", "422", "502", "503", "504"}
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/JobRequirements"
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"job_text": "x", "extra": True},
        {"job_text": True},
        {"job_text": []},
        {"job_text": {}},
    ],
)
def test_strict_request(client, fake_extractor, payload):
    assert client.post("/api/v1/jobs/extract", json=payload).status_code == 422
    assert fake_extractor.received_texts == []


def test_minimum_length(client, fake_extractor):
    assert (
        client.post("/api/v1/jobs/extract", json={"job_text": " x "}).status_code == 200
    )
    assert fake_extractor.received_texts == ["x"]


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"required_skills": None},
        {"required_skills": "Python"},
        {"required_skills": [False]},
        {"required_skills": [], "extra": 1},
    ],
)
def test_strict_response(data):
    with pytest.raises(ValidationError):
        JobRequirements.model_validate(data)
