"""Pure skill matching, independent of providers and HTTP."""

from job_copilot_api.matching.schemas import SkillsMatchingResponse


def normalize_skills(skills: list[str]) -> set[str]:
    return {value for skill in skills if (value := skill.strip().casefold())}


def match_skills(
    candidate_skills: list[str], required_skills: list[str]
) -> SkillsMatchingResponse:
    candidate = normalize_skills(candidate_skills)
    required = normalize_skills(required_skills)
    if not required:
        raise ValueError("At least one nonblank required skill is required.")
    matched = candidate & required
    return SkillsMatchingResponse(
        score=100.0 * len(matched) / len(required),
        matched_skills=sorted(matched),
        missing_skills=sorted(required - candidate),
    )
