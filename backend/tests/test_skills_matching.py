from itertools import permutations

import pytest
from fastapi.testclient import TestClient

from job_copilot_api.main import app
from job_copilot_api.matching.service import match_skills

URL = "/api/v1/matching/skills"


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize(
    "candidate,required,score,matched,missing",
    [
        ([], ["Python"], 0.0, [], ["python"]),
        (["Git"], ["Python"], 0.0, [], ["python"]),
        (["Python", "extra"], ["Python", "SQL"], 50.0, ["python"], ["sql"]),
        (
            ["Python", "SQL"],
            ["Python", "SQL", "Git"],
            200 / 3,
            ["python", "sql"],
            ["git"],
        ),
        (["PYTHON", "extra"], ["Python"], 100.0, ["python"], []),
        (
            [" Python ", "PYTHON", "\t", ""],
            ["python", " PYTHON ", " "],
            100.0,
            ["python"],
            [],
        ),
        (["C", "C++"], ["C", "C++", "C#"], 200 / 3, ["c", "c++"], ["c#"]),
        ([" ", "\t"], ["Git", ""], 0.0, [], ["git"]),
        (
            ["JS", "machine  learning", "cafe"],
            ["JavaScript", "machine learning", "café"],
            0.0,
            [],
            ["café", "javascript", "machine learning"],
        ),
    ],
)
def test_matching(client, candidate, required, score, matched, missing):
    expected = match_skills(candidate, required)
    response = client.post(
        URL,
        json={
            "candidate_skills": candidate,
            "required_skills": required,
        },
    )
    assert response.status_code == 200
    assert response.json() == expected.model_dump()
    assert response.json()["score"] == pytest.approx(score)
    assert response.json()["matched_skills"] == matched
    assert response.json()["missing_skills"] == missing


def test_permutations_and_no_mutation():
    for candidate in permutations([" SQL ", "python", "Python"]):
        for required in permutations(["Python", "Git", "SQL"]):
            candidate_list, required_list = list(candidate), list(required)
            result = match_skills(candidate_list, required_list)
            assert result.matched_skills == ["python", "sql"]
            assert result.missing_skills == ["git"]
            assert result.score == pytest.approx(200 / 3)
            assert candidate_list == list(candidate)
            assert required_list == list(required)


@pytest.mark.parametrize("required", [[], [""], [" ", "\n\t"]])
def test_service_rejects_empty_requirements(required):
    with pytest.raises(ValueError):
        match_skills(["Python"], required)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"candidate_skills": []},
        {"required_skills": ["Python"]},
        {"candidate_skills": [], "required_skills": []},
        {"candidate_skills": [], "required_skills": [" ", ""]},
        {"candidate_skills": [], "required_skills": ["Python"], "extra": True},
        [],
        None,
    ],
)
def test_invalid_payload(client, payload):
    response = (
        client.post(URL, json=payload) if payload is not None else client.post(URL)
    )
    assert response.status_code == 422


@pytest.mark.parametrize("field", ["candidate_skills", "required_skills"])
@pytest.mark.parametrize(
    "value", [None, "Python", {}, 12, True, [123], [True], [None], [{}], [[]]]
)
def test_strict_types(client, field, value):
    payload = {"candidate_skills": [], "required_skills": ["Python"], field: value}
    assert client.post(URL, json=payload).status_code == 422


@pytest.mark.parametrize("field", ["candidate_skills", "required_skills"])
@pytest.mark.parametrize("length", [200, 201])
@pytest.mark.parametrize("blank", [False, True])
def test_raw_skill_length(client, field, length, blank):
    payload = {"candidate_skills": [], "required_skills": ["Python"]}
    value = " " * length if blank else " " + "x" * (length - 2) + " "
    payload[field] = ["Python", value]
    assert client.post(URL, json=payload).status_code == (200 if length == 200 else 422)


@pytest.mark.parametrize("field", ["candidate_skills", "required_skills"])
@pytest.mark.parametrize("count", [1_000, 1_001])
@pytest.mark.parametrize("blank", [False, True])
def test_raw_list_length(client, field, count, blank):
    payload = {"candidate_skills": [], "required_skills": ["Python"]}
    payload[field] = ["Python"] + ([" " if blank else "Python"] * (count - 1))
    assert client.post(URL, json=payload).status_code == (
        200 if count == 1_000 else 422
    )


def test_openapi(client):
    schema = client.get("/openapi.json").json()
    operation = schema["paths"][URL]["post"]
    assert set(operation["responses"]) == {"200", "422"}
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/SkillsMatchingResponse"
    }
    request = schema["components"]["schemas"]["SkillsMatchingRequest"]
    assert request["additionalProperties"] is False
    assert set(request["required"]) == {"candidate_skills", "required_skills"}
    for field in request["required"]:
        prop = request["properties"][field]
        assert prop["maxItems"] == 1_000
        assert prop["items"]["maxLength"] == 200
    result = schema["components"]["schemas"]["SkillsMatchingResponse"]
    assert set(result["required"]) == {"score", "matched_skills", "missing_skills"}
    assert result["properties"]["score"]["minimum"] == 0
    assert result["properties"]["score"]["maximum"] == 100


def test_matching_without_azure_or_network(client, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Matching must not access Azure configuration or clients")

    monkeypatch.setattr(
        "job_copilot_api.config.AzureSettings.from_environment", forbidden
    )
    monkeypatch.setattr("job_copilot_api.cv.azure.create_azure_client", forbidden)
    monkeypatch.setattr("job_copilot_api.cv.service.create_azure_client", forbidden)
    response = client.post(
        URL,
        json={
            "candidate_skills": ["Python"],
            "required_skills": ["Python"],
        },
    )
    assert response.status_code == 200
    assert response.json()["score"] == 100.0
