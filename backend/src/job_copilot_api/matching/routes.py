"""HTTP entry point for deterministic skill coverage."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from job_copilot_api.cv.errors import ExtractionError as CVExtractionError
from job_copilot_api.cv.service import CVExtractor, get_cv_extractor
from job_copilot_api.jobs.errors import ExtractionError as JobExtractionError
from job_copilot_api.jobs.service import JobExtractor, get_job_extractor
from job_copilot_api.matching.analysis import analyze_skills
from job_copilot_api.matching.schemas import (
    MatchingAnalyzeRequest,
    MatchingAnalyzeResponse,
    SkillsMatchingRequest,
    SkillsMatchingResponse,
)
from job_copilot_api.matching.service import match_skills

router = APIRouter(prefix="/api/v1/matching", tags=["matching"])


@router.post("/skills", response_model=SkillsMatchingResponse)
def match_candidate_skills(request: SkillsMatchingRequest) -> SkillsMatchingResponse:
    return match_skills(request.candidate_skills, request.required_skills)


@router.post(
    "/analyze",
    response_model=MatchingAnalyzeResponse,
    responses={
        502: {"description": "Extraction refused, invalid or failed"},
        503: {"description": "Extraction not configured or provider unavailable"},
        504: {"description": "Extraction provider timed out"},
    },
)
def analyze_candidate(
    request: MatchingAnalyzeRequest,
    cv_extractor: Annotated[CVExtractor, Depends(get_cv_extractor)],
    job_extractor: Annotated[JobExtractor, Depends(get_job_extractor)],
) -> MatchingAnalyzeResponse:
    try:
        return analyze_skills(
            request.cv_text, request.job_text, cv_extractor, job_extractor
        )
    except (CVExtractionError, JobExtractionError) as exc:
        raise HTTPException(
            status_code=exc.status_code, detail=exc.public_message
        ) from None
