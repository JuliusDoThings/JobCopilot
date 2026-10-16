"""Strict request and recommendation contracts."""

from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationInfo,
    field_validator,
    model_validator,
)

Nonblank = Annotated[str, StringConstraints(min_length=1)]
Skill = Annotated[str, StringConstraints(min_length=1, max_length=200)]


class ValorizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    # Preserve the source verbatim; strip only to check emptiness.
    cv_text: Annotated[str, StringConstraints(min_length=1, max_length=20_000)]
    target_skills: Annotated[list[Skill], Field(min_length=1, max_length=100)]

    @field_validator("cv_text")
    @classmethod
    def nonblank_cv(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("CV text must not be blank.")
        return value

    @field_validator("target_skills")
    @classmethod
    def trim_skills(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("Target skills must not be blank.")
        return [value.strip() for value in values]


class Recommendation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    skill: Skill
    status: Literal["suggested", "needs_clarification", "no_evidence"]
    evidence: Nonblank | None
    suggestion: Nonblank | None
    clarification_question: Nonblank | None

    @field_validator("skill", "evidence", "suggestion", "clarification_question")
    @classmethod
    def reject_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Text must not be blank.")
        return value

    @model_validator(mode="after")
    def check_state(self, info: ValidationInfo) -> Self:
        present = (
            self.evidence is not None,
            self.suggestion is not None,
            self.clarification_question is not None,
        )
        expected = {
            "suggested": (True, True, False),
            "needs_clarification": (True, False, True),
            "no_evidence": (False, False, False),
        }
        if present != expected[self.status]:
            raise ValueError("Fields do not satisfy the recommendation status.")
        # V1 permits quotation only, never a generated factual claim.
        if self.status == "suggested" and self.suggestion != self.evidence:
            raise ValueError("V1 suggestions must reproduce evidence verbatim.")
        if info.context is not None and self.evidence is not None:
            if self.evidence not in info.context["cv_text"]:
                raise ValueError("Evidence must be an exact CV substring.")
        return self
