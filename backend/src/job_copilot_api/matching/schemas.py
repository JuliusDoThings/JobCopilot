"""Strict HTTP contracts; bounds apply to raw input before normalization."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

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
