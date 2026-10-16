"""HTTP entry point for deterministic skill coverage."""

from fastapi import APIRouter

from job_copilot_api.matching.schemas import (
    SkillsMatchingRequest,
    SkillsMatchingResponse,
)
from job_copilot_api.matching.service import match_skills

router = APIRouter(prefix="/api/v1/matching", tags=["matching"])


@router.post("/skills", response_model=SkillsMatchingResponse)
def match_candidate_skills(request: SkillsMatchingRequest) -> SkillsMatchingResponse:
    return match_skills(request.candidate_skills, request.required_skills)
