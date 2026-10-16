"""Provider contract and default extraction service dependency."""

from collections.abc import Iterator
from typing import Protocol

from job_copilot_api.azure_client import create_azure_client
from job_copilot_api.config import AzureSettings
from job_copilot_api.jobs.azure import AzureJobExtractor
from job_copilot_api.jobs.errors import ExtractionNotConfiguredError
from job_copilot_api.jobs.schemas import JobRequirements


class JobExtractor(Protocol):
    def extract(self, job_text: str) -> JobRequirements: ...


class UnconfiguredExtractor:
    """Default adapter until a real provider is configured."""

    def extract(self, job_text: str) -> JobRequirements:
        raise ExtractionNotConfiguredError


def get_job_extractor() -> Iterator[JobExtractor]:
    settings = AzureSettings.from_environment()
    if settings is None:
        yield UnconfiguredExtractor()
        return
    with create_azure_client(settings) as client:
        yield AzureJobExtractor(client, settings.deployment)
