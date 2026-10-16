"""Synthetic, offline examples and adversarial contract checks."""

from itertools import product

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from job_copilot_api.main import app
from job_copilot_api.valorization.schemas import Recommendation
from job_copilot_api.valorization.service import valorize_cv


@pytest.mark.parametrize(
    ("cv", "skill", "status"),
    [
        ("Expérience en menuiserie.", "Python", "no_evidence"),
        ("Compétences : Python, SQL", "Python", "needs_clarification"),
        ("Python", "Python", "needs_clarification"),
        ("Participation à un projet Python.", "Python", "needs_clarification"),
        ("Développement d'API Python.", "Python", "suggested"),
        ("Développement d’API avec Python.", "Python", "suggested"),
        ("Déploiement avec Docker.", "Docker", "suggested"),
        ("Developed APIs with Python.", "Python", "suggested"),
        ("Deployed applications with Docker.", "Docker", "suggested"),
        ("I worked around Python.", "Python", "needs_clarification"),
        ("Aucune expérience Docker.", "Docker", "no_evidence"),
        ("Je n’ai pas utilisé Docker.", "Docker", "no_evidence"),
        ("Sans connaissance de Docker", "Docker", "no_evidence"),
        ("No Docker experience", "Docker", "no_evidence"),
        ("I have never used Docker", "Docker", "no_evidence"),
        ("I don't use Docker", "Docker", "no_evidence"),
        ("Aucune expérience :\nDocker", "Docker", "no_evidence"),
        ("JavaScript", "Java", "no_evidence"),
        ("Java", "JavaScript", "no_evidence"),
        ("Java, JavaScript", "Java", "needs_clarification"),
        ("Docker Compose", "Docker", "no_evidence"),
        ("Docker", "Docker Compose", "no_evidence"),
        ("Docker Compose", "Docker Compose", "needs_clarification"),
        ("Docker Compose et Docker", "Docker", "needs_clarification"),
        ("Déploiement de conteneurs", "Docker", "no_evidence"),
        ("PostgreSQL", "SQL", "no_evidence"),
        ("C++ et C#", "C", "no_evidence"),
        ("C++", "C++", "needs_clarification"),
        ("C#", "C#", "needs_clarification"),
        ("ASP.NET", ".NET", "no_evidence"),
        (".NET", ".NET", "needs_clarification"),
        ("Automatisation avec python.", "Python", "suggested"),
        ("Objectif :\nDéveloppement d'API Python.", "Python", "needs_clarification"),
        ("Exemple :\nDéploiement avec Docker.", "Docker", "needs_clarification"),
        ("Déploiement avec Docker souhaité.", "Docker", "needs_clarification"),
        ("Expert Python, gain de 50 %.", "Python", "needs_clarification"),
        (
            "Développement d'API Python et déploiement avec Docker.",
            "Python",
            "needs_clarification",
        ),
    ],
)
def test_lexical_policy(cv: str, skill: str, status: str) -> None:
    recommendation = valorize_cv(cv, [skill])[0]
    assert recommendation.status == status
    if recommendation.evidence is not None:
        assert recommendation.evidence in cv
    if status == "suggested":
        assert recommendation.suggestion == recommendation.evidence
        assert recommendation.clarification_question is None
    elif status == "needs_clarification":
        assert recommendation.suggestion is None
        assert skill in recommendation.clarification_question
    else:
        assert recommendation.evidence is None
        assert recommendation.suggestion is None
        assert recommendation.clarification_question is None


def test_source_and_target_order_are_preserved() -> None:
    cv = "  Compétences : SQL\n\tDéveloppement d’API avec pYtHoN.  \n"
    results = valorize_cv(cv, ["Python", "SQL", "Docker", " Python "])
    assert [item.skill for item in results] == ["Python", "SQL", "Docker", "Python"]
    assert results[0].evidence == "Développement d’API avec pYtHoN."
    assert results[0] == results[3]
    assert results[1].evidence == "Compétences : SQL"
    assert [item.status for item in results] == [
        "suggested",
        "needs_clarification",
        "no_evidence",
        "suggested",
    ]


@pytest.mark.parametrize("status", ["suggested", "needs_clarification", "no_evidence"])
@pytest.mark.parametrize("present", list(product([False, True], repeat=3)))
def test_all_state_field_combinations(status: str, present: tuple[bool, ...]) -> None:
    fields = ("evidence", "suggestion", "clarification_question")
    data = dict(zip(fields, ["Python" if flag else None for flag in present]))
    data.update(skill="Python", status=status)
    valid = {
        "suggested": (True, True, False),
        "needs_clarification": (True, False, True),
        "no_evidence": (False, False, False),
    }
    if present == valid[status]:
        Recommendation.model_validate(data, context={"cv_text": "Python"})
    else:
        with pytest.raises(ValidationError):
            Recommendation.model_validate(data)


@pytest.mark.parametrize("field", ["skill", "evidence", "suggestion"])
@pytest.mark.parametrize("value", ["", " \n", 123])
def test_invalid_recommendation_text(field: str, value: object) -> None:
    data = dict(
        skill="Python",
        status="suggested",
        evidence="Python",
        suggestion="Python",
        clarification_question=None,
    )
    data[field] = value
    with pytest.raises(ValidationError):
        Recommendation.model_validate(data)


def test_evidence_source_and_suggestion_fidelity_are_validated() -> None:
    data = dict(
        skill="Python",
        status="suggested",
        evidence="Python",
        suggestion="Expert Python",
        clarification_question=None,
    )
    with pytest.raises(ValidationError):
        Recommendation.model_validate(data)
    data["suggestion"] = "Python"
    with pytest.raises(ValidationError):
        Recommendation.model_validate(data, context={"cv_text": "Java"})


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"cv_text": "Python"},
        {"target_skills": ["Python"]},
        {"cv_text": "", "target_skills": ["Python"]},
        {"cv_text": " \n", "target_skills": ["Python"]},
        {"cv_text": "x" * 20_001, "target_skills": ["Python"]},
        {"cv_text": 123, "target_skills": ["Python"]},
        {"cv_text": None, "target_skills": ["Python"]},
        {"cv_text": "Python", "target_skills": []},
        {"cv_text": "Python", "target_skills": [""]},
        {"cv_text": "Python", "target_skills": [" \t"]},
        {"cv_text": "Python", "target_skills": [123]},
        {"cv_text": "Python", "target_skills": [None]},
        {"cv_text": "Python", "target_skills": ["x" * 201]},
        {"cv_text": "Python", "target_skills": ["Python"] * 101},
        {"cv_text": "Python", "target_skills": "Python"},
        {"cv_text": "Python", "target_skills": None},
        {"cv_text": "Python", "target_skills": ["Python"], "job_text": "Docker"},
    ],
)
def test_invalid_api_payload(payload: dict[str, object]) -> None:
    with TestClient(app) as client:
        assert client.post("/api/v1/cv/valorization", json=payload).status_code == 422


def test_api_without_body() -> None:
    with TestClient(app) as client:
        assert client.post("/api/v1/cv/valorization").status_code == 422


def test_api_returns_three_states_without_configured_provider() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/cv/valorization",
            json={
                "cv_text": "Développement d'API Python.\nCompétences : SQL",
                "target_skills": ["Python", "SQL", "Docker"],
            },
        )
        assert response.status_code == 200
        assert response.json() == [
            {
                "skill": "Python",
                "status": "suggested",
                "evidence": "Développement d'API Python.",
                "suggestion": "Développement d'API Python.",
                "clarification_question": None,
            },
            {
                "skill": "SQL",
                "status": "needs_clarification",
                "evidence": "Compétences : SQL",
                "suggestion": None,
                "clarification_question": (
                    "Quelle activité avez-vous réalisée avec SQL, "
                    "et quel était votre rôle exact ?"
                ),
            },
            {
                "skill": "Docker",
                "status": "no_evidence",
                "evidence": None,
                "suggestion": None,
                "clarification_question": None,
            },
        ]


def test_api_input_bounds_and_openapi() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/cv/valorization",
            json={"cv_text": "x" * 20_000, "target_skills": ["s" * 200] * 100},
        )
        assert response.status_code == 200
        assert len(response.json()) == 100
        operation = client.get("/openapi.json").json()["paths"][
            "/api/v1/cv/valorization"
        ]["post"]
        assert set(operation["responses"]) == {"200", "422"}


def test_service_validates_inputs_itself() -> None:
    with pytest.raises(ValidationError):
        valorize_cv("Python", [])
