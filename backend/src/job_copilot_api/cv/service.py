"""Provider contract and default extraction service dependency."""

from typing import Protocol

from job_copilot_api.cv.schemas import CVProfile


class CVExtractor(Protocol):
    def extract(self, cv_text: str) -> CVProfile: ...


class ExtractionNotConfiguredError(Exception):
    """No extraction provider has been configured."""


class UnconfiguredExtractor:
    """Default adapter until a real provider is configured."""

    def extract(self, cv_text: str) -> CVProfile:
        raise ExtractionNotConfiguredError


def get_cv_extractor() -> CVExtractor:
    return UnconfiguredExtractor()
