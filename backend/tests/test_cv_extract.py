from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from job_copilot_api.cv.schemas import CVProfile
from job_copilot_api.cv.service import get_cv_extractor
from job_copilot_api.main import app

PROFILE = CVProfile(
    skills=["Python"],
    experiences=["Projet fictif de développement"],
    education=["Formation fictive en informatique"],
)


class FakeExtractor:
    def __init__(self, profile: CVProfile = PROFILE) -> None:
        self.profile = profile
        self.received_texts: list[str] = []

    def extract(self, cv_text: str) -> CVProfile:
        self.received_texts.append(cv_text)
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
    app.dependency_overrides[get_cv_extractor] = lambda: fake
    return fake


def test_extract_valid_cv(client: TestClient, fake_extractor: FakeExtractor) -> None:
    response = client.post(
        "/api/v1/cv/extract", json={"cv_text": " \n CV entièrement fictif. \t "}
    )

    assert response.status_code == 200
    assert response.json() == PROFILE.model_dump()
    assert fake_extractor.received_texts == ["CV entièrement fictif."]


@pytest.mark.parametrize(
    "payload",
    [
        {"cv_text": ""},
        {"cv_text": "   \n\t "},
        {"cv_text": "x" * 20_001},
        {"cv_text": " \n" + "x" * 20_001 + "\t "},
        {"cv_text": None},
        {"cv_text": 123},
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
    response = client.post("/api/v1/cv/extract", json=payload)

    assert response.status_code == 422
    assert fake_extractor.received_texts == []


@pytest.mark.parametrize("padding", ["", " \n\t "])
def test_maximum_length_after_strip(
    client: TestClient, fake_extractor: FakeExtractor, padding: str
) -> None:
    response = client.post(
        "/api/v1/cv/extract", json={"cv_text": padding + "x" * 20_000 + padding}
    )

    assert response.status_code == 200
    assert response.json() == PROFILE.model_dump()
    assert fake_extractor.received_texts == ["x" * 20_000]


def test_empty_profile_lists(client: TestClient, fake_extractor: FakeExtractor) -> None:
    fake_extractor.profile = CVProfile(skills=[], experiences=[], education=[])

    response = client.post("/api/v1/cv/extract", json={"cv_text": "CV fictif."})

    assert response.status_code == 200
    assert response.json() == {"skills": [], "experiences": [], "education": []}


@pytest.mark.parametrize("missing_field", ["skills", "experiences", "education"])
def test_profile_fields_are_required(missing_field: str) -> None:
    data = PROFILE.model_dump()
    del data[missing_field]

    with pytest.raises(ValidationError):
        CVProfile.model_validate(data)


def test_unconfigured_provider(client: TestClient) -> None:
    response = client.post("/api/v1/cv/extract", json={"cv_text": "CV fictif."})

    assert response.status_code == 503
    assert response.json() == {"detail": "CV extraction service is not configured."}


def test_openapi_exposes_extraction(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    operation = response.json()["paths"]["/api/v1/cv/extract"]["post"]
    assert set(operation["responses"]) == {"200", "422", "502", "503", "504"}
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/CVProfile"
    }
