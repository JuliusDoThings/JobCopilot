"""Provider contract and default extraction service dependency."""

from collections.abc import Iterator
from typing import Protocol

from job_copilot_api.config import AzureSettings
from job_copilot_api.cv.azure import AzureCVExtractor, create_azure_client
from job_copilot_api.cv.errors import ExtractionNotConfiguredError
from job_copilot_api.cv.schemas import CVProfile


class CVExtractor(Protocol):
    def extract(self, cv_text: str) -> CVProfile: ...


class UnconfiguredExtractor:
    """Default adapter until a real provider is configured."""

    def extract(self, cv_text: str) -> CVProfile:
        raise ExtractionNotConfiguredError


def get_cv_extractor() -> Iterator[CVExtractor]:
    settings = AzureSettings.from_environment()
    if settings is None:
        yield UnconfiguredExtractor()
        return
    with create_azure_client(settings) as client:
        yield AzureCVExtractor(client, settings.deployment)
