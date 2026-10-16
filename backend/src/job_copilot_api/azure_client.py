"""Shared secure Azure client factory; no domain extraction logic."""

from openai import DefaultHttpxClient, OpenAI

from job_copilot_api.config import AzureSettings


def create_azure_client(settings: AzureSettings) -> OpenAI:
    return OpenAI(
        base_url=settings.base_url,
        api_key=settings.api_key,
        timeout=30.0,
        max_retries=1,
        http_client=DefaultHttpxClient(follow_redirects=False),
    )
