"""Lexical evidence selection, without provider or matching dependencies."""

import re

from job_copilot_api.valorization.schemas import Recommendation, ValorizationRequest

# Keep punctuation such as C++, C#, .NET and decimal/version dots intact.
SEGMENTS = re.compile(r"[^\n\r;!?]+")
NEGATION = re.compile(
    r"\b(?:aucun\w*|sans|jamais|pas|ni|non|not|no|never|without|lack\w*)\b"
    r"|\b(?:n['’]|ne\s)|\b(?:don['’]t|haven['’]t|isn['’]t|cannot|can['’]t)\b",
    re.IGNORECASE,
)
UNCERTAIN_CONTEXT = re.compile(
    r"\b(?:objectif\w*|souhait\w*|appren\w*|formation\w*|exemple\w*|"
    r"offre|recherch\w*|futur\w*|prév\w*|envisag\w*|si|"
    r"goal\w*|wish\w*|learn\w*|training|example\w*|would|could|if|"
    r"planned|wanted|job description)\b",
    re.IGNORECASE,
)


def _mentions(text: str, skill: str) -> bool:
    # Symbol boundaries prevent C matching C++/C#, or .NET matching ASP.NET.
    pattern = rf"(?<![\w.+#-]){re.escape(skill)}(?![\w+#-])"
    if not re.search(pattern, text, re.IGNORECASE):
        return False
    # Compose is a distinct compound skill, not evidence of standalone Docker.
    if skill.casefold() == "docker":
        return bool(re.search(pattern + r"(?!\s+compose\b)", text, re.IGNORECASE))
    return True


def _explicit_activity(text: str, skill: str) -> bool:
    # Closed, full-segment templates: no arbitrary suffix, proficiency or metrics.
    activity = (
        r"(?:Développement d['’]API|Développement d['’]API avec|"
        r"Déploiement avec|Automatisation avec|"
        r"Developed APIs? with|Deployed applications with|Automated tasks with)"
    )
    return bool(
        re.fullmatch(rf"{activity}\s+{re.escape(skill)}\.?", text, re.IGNORECASE)
    )


def valorize_cv(cv_text: str, target_skills: list[str]) -> list[Recommendation]:
    """Return one result per target, in order, preserving duplicates and source."""
    request = ValorizationRequest(cv_text=cv_text, target_skills=target_skills)
    segments = [match.group().strip() for match in SEGMENTS.finditer(cv_text)]
    # A context heading can govern the next line. Prefer omission over treating
    # a negative heading followed by a skill list as positive evidence.
    positive_segments = [
        (text, segments[index - 1] if index else "")
        for index, text in enumerate(segments)
        if not NEGATION.search(text)
        and not (
            index
            and NEGATION.search(segments[index - 1])
            and not segments[index - 1].endswith(".")
        )
    ]
    results = []
    for skill in request.target_skills:
        candidates = [
            (text, previous)
            for text, previous in positive_segments
            if _mentions(text, skill)
        ]
        explicit = next(
            (
                text
                for text, previous in candidates
                if not UNCERTAIN_CONTEXT.search(text)
                and not (
                    UNCERTAIN_CONTEXT.search(previous) and not previous.endswith(".")
                )
                and _explicit_activity(text, skill)
            ),
            None,
        )
        evidence = explicit or (candidates[0][0] if candidates else None)
        status = (
            "suggested"
            if explicit
            else "needs_clarification"
            if evidence
            else "no_evidence"
        )
        results.append(
            Recommendation.model_validate(
                {
                    "skill": skill,
                    "status": status,
                    "evidence": evidence,
                    "suggestion": explicit,
                    "clarification_question": (
                        f"Quelle activité avez-vous réalisée avec {skill}, "
                        "et quel était votre rôle exact ?"
                        if status == "needs_clarification"
                        else None
                    ),
                },
                context={"cv_text": cv_text},
            )
        )
    return results
