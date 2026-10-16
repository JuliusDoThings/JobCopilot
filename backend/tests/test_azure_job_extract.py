import json
from collections.abc import Callable, Iterator

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import OpenAI

from job_copilot_api.azure_client import create_azure_client
from job_copilot_api.config import AzureSettings
from job_copilot_api.jobs.azure import AzureJobExtractor
from job_copilot_api.jobs.errors import ExtractionError
from job_copilot_api.jobs.service import get_job_extractor
from job_copilot_api.main import app

JOB_TEXT = (
    "Annonce entièrement fictive, marqueur-confidentiel-test. Compétence : Python."
)
KEY = "fictional-secret-marker"
PROFILE = {"required_skills": ["Python"]}


def sdk_response(
    content: object = PROFILE, *, status: str = "completed", refusal: bool = False
) -> dict[str, object]:
    message_content = (
        {"type": "refusal", "refusal": JOB_TEXT + KEY}
        if refusal
        else {"type": "output_text", "text": json.dumps(content), "annotations": []}
    )
    return {
        "id": "resp_fictional",
        "object": "response",
        "created_at": 0,
        "model": "gpt-4.1-mini",
        "status": status,
        "error": None,
        "incomplete_details": None
        if status == "completed"
        else {"reason": "max_output_tokens"},
        "output": [
            {
                "id": "msg_fictional",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [message_content],
            }
        ],
        "parallel_tool_calls": False,
        "tools": [],
        "tool_choice": "auto",
    }


@pytest.fixture
def client() -> Iterator[TestClient]:
    previous = app.dependency_overrides.copy()
    app.dependency_overrides.clear()
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest.fixture
def install_sdk(
    client: TestClient,
) -> Iterator[Callable[[Callable[[httpx.Request], httpx.Response]], OpenAI]]:
    clients: list[OpenAI] = []

    def install(handler: Callable[[httpx.Request], httpx.Response]) -> OpenAI:
        sdk = OpenAI(
            api_key=KEY,
            base_url="https://fictional.openai.azure.com/openai/v1/",
            timeout=30.0,
            max_retries=1,
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        clients.append(sdk)
        app.dependency_overrides[get_job_extractor] = lambda: AzureJobExtractor(
            sdk, "gpt-4.1-mini"
        )
        return sdk

    yield install
    for sdk in clients:
        sdk.close()


def test_sdk_success_and_strict_schema(
    client: TestClient, install_sdk: Callable
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=sdk_response())

    install_sdk(handler)
    response = client.post(
        "/api/v1/jobs/extract", json={"job_text": " " + JOB_TEXT + " "}
    )
    assert response.status_code == 200
    assert response.json() == PROFILE
    assert len(requests) == 1
    body = json.loads(requests[0].content)
    assert requests[0].url.path == "/openai/v1/responses"
    assert body["model"] == "gpt-4.1-mini"
    assert body["input"][1] == {"role": "user", "content": JOB_TEXT}
    assert JOB_TEXT not in body["input"][0]["content"]
    assert body["store"] is False
    schema = body["text"]["format"]
    assert schema["type"] == "json_schema"
    assert schema["strict"] is True
    assert schema["schema"]["additionalProperties"] is False
    assert set(schema["schema"]["required"]) == set(PROFILE)


@pytest.mark.parametrize(
    "content",
    [
        {},
        {"required_skills": [123]},
        {**PROFILE, "extra": "unwanted"},
        None,
    ],
)
def test_invalid_structured_response(
    client: TestClient, install_sdk: Callable, content: object
) -> None:
    install_sdk(lambda request: httpx.Response(200, json=sdk_response(content)))
    response = client.post("/api/v1/jobs/extract", json={"job_text": JOB_TEXT})
    assert response.status_code == 502
    assert response.json() == {
        "detail": "Job extraction provider returned an invalid response."
    }


@pytest.mark.parametrize(
    "refusal,status,detail",
    [
        (True, "completed", "Job extraction was refused by the provider."),
        (False, "incomplete", "Job extraction provider returned an invalid response."),
        (False, "failed", "Job extraction provider returned an invalid response."),
    ],
)
def test_refused_or_incomplete_response(
    client: TestClient, install_sdk: Callable, refusal: bool, status: str, detail: str
) -> None:
    install_sdk(
        lambda request: httpx.Response(
            200, json=sdk_response(status=status, refusal=refusal)
        )
    )
    response = client.post("/api/v1/jobs/extract", json={"job_text": JOB_TEXT})
    assert response.status_code == 502
    assert response.json() == {"detail": detail}
    assert KEY not in response.text
    assert JOB_TEXT not in response.text


@pytest.mark.parametrize(
    "failure,expected_code,expected_attempts",
    [
        ("timeout", 504, 2),
        ("connection", 503, 2),
        (408, 503, 2),
        (409, 503, 2),
        (429, 503, 2),
        (500, 503, 2),
        (401, 502, 1),
        (400, 502, 1),
    ],
)
def test_sdk_errors_and_retry_limit(
    client: TestClient,
    install_sdk: Callable,
    failure: str | int,
    expected_code: int,
    expected_attempts: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    attempts: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout(JOB_TEXT + KEY, request=request)
        if failure == "connection":
            raise httpx.ConnectError(JOB_TEXT + KEY, request=request)
        return httpx.Response(
            int(failure),
            json={"error": {"message": JOB_TEXT + KEY, "type": "fictional_error"}},
            headers={"retry-after-ms": "1"},
        )

    sdk = install_sdk(handler)
    assert sdk.max_retries == 1
    response = client.post("/api/v1/jobs/extract", json={"job_text": JOB_TEXT})
    assert response.status_code == expected_code
    assert len(attempts) == expected_attempts
    assert KEY not in response.text + caplog.text
    assert JOB_TEXT not in response.text + caplog.text


def test_sdk_recovers_on_single_retry(
    client: TestClient, install_sdk: Callable
) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(
                503,
                json={"error": {"message": "unavailable"}},
                headers={"retry-after-ms": "1"},
            )
        return httpx.Response(200, json=sdk_response())

    install_sdk(handler)
    response = client.post("/api/v1/jobs/extract", json={"job_text": JOB_TEXT})
    assert response.status_code == 200
    assert attempts == 2


def test_client_configuration() -> None:
    settings = AzureSettings("https://fictional.openai.azure.com", "gpt-4.1-mini", KEY)
    with create_azure_client(settings) as sdk:
        assert sdk.max_retries == 1
        assert sdk.timeout == 30.0
        assert str(sdk.base_url) == "https://fictional.openai.azure.com/openai/v1/"
    assert KEY not in repr(settings)


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://fictional.openai.azure.com",
        "https://fictional.openai.azure.com/openai/v1/",
        "https://fictional.services.ai.azure.com",
        "https://fictional.services.ai.azure.com/openai/v1/",
    ],
)
def test_environment_selects_azure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, endpoint: str
) -> None:
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", endpoint)
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", KEY)
    sdk = OpenAI(
        api_key=KEY,
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=sdk_response())
            )
        ),
    )
    monkeypatch.setattr(
        "job_copilot_api.jobs.service.create_azure_client", lambda settings: sdk
    )
    response = client.post("/api/v1/jobs/extract", json={"job_text": JOB_TEXT})
    assert response.status_code == 200
    assert response.json() == PROFILE
    assert sdk.is_closed()


@pytest.mark.parametrize(
    "endpoint",
    [
        "",
        "http://fictional.example",
        "https://[",
        "https://user:password@fictional.example",
        "https://fictional.example/projects/test",
        "https://fictional.example?key=fictional",
    ],
)
def test_missing_or_invalid_configuration(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, endpoint: str
) -> None:
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", endpoint)
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", KEY)
    response = client.post("/api/v1/jobs/extract", json={"job_text": JOB_TEXT})
    assert response.status_code == 503
    assert response.json() == {"detail": "Job extraction service is not configured."}


@pytest.mark.parametrize("missing", ["AZURE_OPENAI_DEPLOYMENT", "AZURE_OPENAI_API_KEY"])
def test_partial_configuration(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://fictional.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", KEY)
    monkeypatch.delenv(missing)
    response = client.post("/api/v1/jobs/extract", json={"job_text": JOB_TEXT})
    assert response.status_code == 503


@pytest.mark.parametrize(
    "body",
    [
        {**sdk_response(), "output": []},
        {**sdk_response(), "output": None},
        {},
    ],
)
def test_missing_response_fields(
    client: TestClient, install_sdk: Callable, body: dict[str, object]
) -> None:
    install_sdk(lambda request: httpx.Response(200, json=body))
    response = client.post("/api/v1/jobs/extract", json={"job_text": JOB_TEXT})
    assert response.status_code == 502
    assert response.json() == {
        "detail": "Job extraction provider returned an invalid response."
    }


def test_invalid_domain_never_creates_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://attacker.example")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "fictional-key")

    def reject_creation(*args: object) -> None:
        pytest.fail("An invalid domain must never create a client")

    monkeypatch.setattr(
        "job_copilot_api.jobs.service.create_azure_client", reject_creation
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/jobs/extract", json={"job_text": "Annonce fictive"}
        )
    assert response.status_code == 503


@pytest.mark.parametrize("domain", ["openai.azure.com", "services.ai.azure.com"])
def test_redirect_cannot_forward_job_or_key(
    monkeypatch: pytest.MonkeyPatch, domain: str
) -> None:
    requests: list[httpx.Request] = []

    def redirect(self: httpx.HTTPTransport, request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(307, headers={"location": "https://attacker.example"})

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", redirect)
    settings = AzureSettings(
        f"https://resource.{domain}", "gpt-4.1-mini", "fictional-key"
    )
    with create_azure_client(settings) as sdk:
        with pytest.raises(ExtractionError):
            AzureJobExtractor(sdk, settings.deployment).extract("Annonce fictive")
    assert len(requests) == 1
    assert requests[0].url.host == f"resource.{domain}"


def test_fictional_corpus_transport_and_instruction_separation(client, install_sdk):
    from pathlib import Path

    from job_copilot_api.jobs.azure import EXTRACTION_INSTRUCTIONS

    cases = json.loads(
        (
            Path(__file__).resolve().parents[1] / "evaluation/fictional_jobs.json"
        ).read_text()
    )
    for case in cases:
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(
                200,
                json=sdk_response(
                    {
                        "required_skills": case["expected_required_skills"],
                    }
                ),
            )

        install_sdk(handler)
        response = client.post(
            "/api/v1/jobs/extract", json={"job_text": case["job_text"]}
        )
        assert response.status_code == 200
        assert response.json()["required_skills"] == case["expected_required_skills"]
        body = json.loads(requests[0].content)
        assert body["input"] == [
            {"role": "system", "content": EXTRACTION_INSTRUCTIONS},
            {"role": "user", "content": case["job_text"]},
        ]
        assert body["max_output_tokens"] == 2_000


def test_malformed_json_response(client, install_sdk):
    body = sdk_response()
    body["output"][0]["content"][0]["text"] = "not-json " + KEY + JOB_TEXT
    install_sdk(lambda request: httpx.Response(200, json=body))
    response = client.post("/api/v1/jobs/extract", json={"job_text": JOB_TEXT})
    assert response.status_code == 502
    assert KEY not in response.text and JOB_TEXT not in response.text


def test_client_closed_after_provider_failure(client, monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://fictional.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", KEY)
    sdk = OpenAI(
        api_key=KEY,
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(401, json={"error": {"message": KEY}})
            )
        ),
    )
    monkeypatch.setattr(
        "job_copilot_api.jobs.service.create_azure_client", lambda _: sdk
    )
    response = client.post("/api/v1/jobs/extract", json={"job_text": JOB_TEXT})
    assert response.status_code == 502
    assert sdk.is_closed()


def test_adapter_revalidates_injected_client():
    from types import SimpleNamespace

    from job_copilot_api.jobs.errors import InvalidExtractionError

    for parsed in (
        None,
        {"required_skills": [123]},
        {"required_skills": [], "extra": 1},
    ):
        fake = SimpleNamespace(
            responses=SimpleNamespace(
                parse=lambda **_: SimpleNamespace(
                    output=[], status="completed", output_parsed=parsed
                )
            )
        )
        with pytest.raises(InvalidExtractionError):
            AzureJobExtractor(fake, "gpt-4.1-mini").extract(JOB_TEXT)
