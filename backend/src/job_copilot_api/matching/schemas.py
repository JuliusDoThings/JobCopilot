"""Strict HTTP contracts; bounds apply to raw input before normalization."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from job_copilot_api.cv.schemas import CVExtractRequest
from job_copilot_api.jobs.schemas import JobExtractRequest

Skill = Annotated[str, StringConstraints(strict=True, max_length=200)]
SkillList = Annotated[list[Skill], Field(max_length=1_000)]


class SkillsMatchingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    candidate_skills: SkillList
    required_skills: SkillList

    @field_validator("required_skills")
    @classmethod
    def require_nonblank_skill(cls, skills: list[str]) -> list[str]:
        if not any(skill.strip().casefold() for skill in skills):
            raise ValueError("At least one nonblank required skill is required.")
        return skills


class SkillsMatchingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    score: float = Field(ge=0, le=100)
    matched_skills: list[str]
    missing_skills: list[str]


class MatchingAnalyzeRequest(CVExtractRequest, JobExtractRequest):
    """Reuse both text contracts while rejecting extra fields and coercions."""

    model_config = ConfigDict(extra="forbid", strict=True)


class ScoredAnalysis(SkillsMatchingResponse):
    status: Literal["scored"] = "scored"
    reason: None = None


class NotScorableAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    status: Literal["not_scorable"] = "not_scorable"
    score: None = None
    matched_skills: list[str] = Field(default_factory=list, max_length=0)
    missing_skills: list[str] = Field(default_factory=list, max_length=0)
    reason: Literal["no_explicit_required_skills"] = "no_explicit_required_skills"


MatchingAnalyzeResponse = Annotated[
    ScoredAnalysis | NotScorableAnalysis, Field(discriminator="status")
]
