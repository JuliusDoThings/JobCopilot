"""Pure metrics shared by offline evaluation scripts, not extraction adapters."""


def normalize(value: str) -> str:
    return value.strip().casefold()


def score_skills(actual: list[str], expected: list[str]) -> dict:
    extracted = {normalize(s) for s in actual}
    wanted = {normalize(s) for s in expected}
    tp = len(extracted & wanted)
    precision = tp / len(extracted) if extracted else float(not wanted)
    recall = tp / len(wanted) if wanted else 1.0
    return {
        "true_positives": tp,
        "false_positives": sorted(extracted - wanted),
        "false_negatives": sorted(wanted - extracted),
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0,
    }
