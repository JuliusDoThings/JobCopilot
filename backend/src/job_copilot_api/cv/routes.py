"""HTTP contract for structured CV extraction."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from job_copilot_api.cv.schemas import CVExtractRequest, CVProfile
from job_copilot_api.cv.service import (
    CVExtractor,
    ExtractionNotConfiguredError,
    get_cv_extractor,
)

router = APIRouter(prefix="/api/v1/cv", tags=["cv"])


@router.post(
    "/extract",
    response_model=CVProfile,
    responses={503: {"description": "Extraction service is not configured"}},
)
def extract_cv(
    request: CVExtractRequest,
    extractor: Annotated[CVExtractor, Depends(get_cv_extractor)],
) -> CVProfile:
    try:
        return extractor.extract(request.cv_text)
    except ExtractionNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CV extraction service is not configured.",
        ) from exc
