"""Sequential extraction and lexical matching, without provider management."""

from job_copilot_api.cv.service import CVExtractor
from job_copilot_api.jobs.service import JobExtractor
from job_copilot_api.matching.schemas import (
    MatchingAnalyzeResponse,
    NotScorableAnalysis,
    ScoredAnalysis,
)
from job_copilot_api.matching.service import match_skills, normalize_skills


def analyze_skills(
    cv_text: str, job_text: str, cv_extractor: CVExtractor, job_extractor: JobExtractor
) -> MatchingAnalyzeResponse:
    profile = cv_extractor.extract(cv_text)
    requirements = job_extractor.extract(job_text)
    if not normalize_skills(requirements.required_skills):
        return NotScorableAnalysis()
    result = match_skills(profile.skills, requirements.required_skills)
    return ScoredAnalysis(**result.model_dump())
