"""Versioned endpoint for offline CV valorization."""

from fastapi import APIRouter

from job_copilot_api.valorization.schemas import Recommendation, ValorizationRequest
from job_copilot_api.valorization.service import valorize_cv

router = APIRouter(prefix="/api/v1/cv", tags=["cv"])


@router.post("/valorization", response_model=list[Recommendation])
def valorize(request: ValorizationRequest) -> list[Recommendation]:
    return valorize_cv(request.cv_text, request.target_skills)
