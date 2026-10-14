import httpx
import pytest
from fastapi.testclient import TestClient

from job_copilot_api.config import AzureSettings
from job_copilot_api.cv.azure import AzureCVExtractor, create_azure_client
from job_copilot_api.cv.errors import ExtractionError
from job_copilot_api.main import app


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://attacker.example",
        "https://openai.azure.com",
        "https://resource.openai.azure.com.attacker.example",
        "https://attacker-openai.azure.com",
        "https://nested.resource.openai.azure.com",
        "https://resource.openai.azure.com@attacker.example",
        "https://attacker.example@resource.openai.azure.com",
        "https://resource.openai.azure.com:8443",
        "https://127.0.0.1",
        "https://[::1]",
        "https://resource.openai.azure.com\\@attacker.example",
        "https://resource.openai.azure.com\n",
        "https://resource.openai.azure.com/%2e%2e/",
        "https://resource.openai.azure.com#fragment",
        "https://resource.openai.azure.com?redirect=attacker.example",
        "https://resource.openai.azure.com.",
        "https://resource.openai.azure.com//",
    ],
)
def test_unsafe_endpoint_rejected(endpoint: str) -> None:
    with pytest.raises(ValueError, match="endpoint is not allowed"):
        AzureSettings(endpoint, "gpt-4.1-mini", "fictional-key")


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://resource.openai.azure.com",
        "https://resource.openai.azure.com/",
        "https://resource.openai.azure.com:443",
        "https://resource.openai.azure.com/openai/v1/",
        "https://my-resource-123.openai.azure.com/openai/v1",
    ],
)
def test_allowed_endpoint(endpoint: str) -> None:
    settings = AzureSettings(endpoint, "gpt-4.1-mini", "fictional-key")
    assert settings.base_url.endswith("/openai/v1/")


def test_invalid_domain_never_creates_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://attacker.example")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "fictional-key")

    def reject_creation(*args: object) -> None:
        pytest.fail("An invalid domain must never create a client")

    monkeypatch.setattr(
        "job_copilot_api.cv.service.create_azure_client", reject_creation
    )
    with TestClient(app) as client:
        response = client.post("/api/v1/cv/extract", json={"cv_text": "CV fictif"})
    assert response.status_code == 503


def test_redirect_cannot_forward_cv_or_key(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[httpx.Request] = []

    def redirect(self: httpx.HTTPTransport, request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(307, headers={"location": "https://attacker.example"})

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", redirect)
    settings = AzureSettings(
        "https://resource.openai.azure.com", "gpt-4.1-mini", "fictional-key"
    )
    with create_azure_client(settings) as sdk:
        with pytest.raises(ExtractionError):
            AzureCVExtractor(sdk, settings.deployment).extract("CV fictif")
    assert len(requests) == 1
    assert requests[0].url.host == "resource.openai.azure.com"
