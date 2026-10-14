"""Input validation and structured extraction output."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


class CVExtractRequest(BaseModel):
    cv_text: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=20_000),
    ]


class CVProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    skills: list[str]
    experiences: list[str]
    education: list[str]
