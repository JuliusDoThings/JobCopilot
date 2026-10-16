"""HTTP contract for structured Job extraction."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from job_copilot_api.jobs.errors import ExtractionError
from job_copilot_api.jobs.schemas import JobExtractRequest, JobRequirements
from job_copilot_api.jobs.service import (
    JobExtractor,
    get_job_extractor,
)

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.post(
    "/extract",
    response_model=JobRequirements,
    responses={
        502: {
            "description": "Extraction failed, was refused or returned invalid output"
        },
        503: {"description": "Extraction is not configured or provider is unavailable"},
        504: {"description": "Extraction provider timed out"},
    },
)
def extract_job(
    request: JobExtractRequest,
    extractor: Annotated[JobExtractor, Depends(get_job_extractor)],
) -> JobRequirements:
    try:
        return extractor.extract(request.job_text)
    except ExtractionError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.public_message,
        ) from None
