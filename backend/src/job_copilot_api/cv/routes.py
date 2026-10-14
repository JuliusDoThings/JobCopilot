"""HTTP contract for structured CV extraction."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from job_copilot_api.cv.errors import ExtractionError
from job_copilot_api.cv.schemas import CVExtractRequest, CVProfile
from job_copilot_api.cv.service import (
    CVExtractor,
    get_cv_extractor,
)

router = APIRouter(prefix="/api/v1/cv", tags=["cv"])


@router.post(
    "/extract",
    response_model=CVProfile,
    responses={
        502: {
            "description": "Extraction failed, was refused or returned invalid output"
        },
        503: {"description": "Extraction is not configured or provider is unavailable"},
        504: {"description": "Extraction provider timed out"},
    },
)
def extract_cv(
    request: CVExtractRequest,
    extractor: Annotated[CVExtractor, Depends(get_cv_extractor)],
) -> CVProfile:
    try:
        return extractor.extract(request.cv_text)
    except ExtractionError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.public_message,
        ) from None
