"""Strict request and structured job requirements output."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


class JobExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    job_text: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=20_000),
    ]


class JobRequirements(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    required_skills: list[str]
