"""Input validation and structured extraction output."""

from typing import Annotated

from pydantic import BaseModel, StringConstraints


class CVExtractRequest(BaseModel):
    cv_text: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=20_000),
    ]


class CVProfile(BaseModel):
    skills: list[str]
    experiences: list[str]
    education: list[str]
