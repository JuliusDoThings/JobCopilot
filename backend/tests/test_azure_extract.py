import json
from collections.abc import Callable, Iterator

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import OpenAI

from job_copilot_api.config import AzureSettings
from job_copilot_api.cv.azure import AzureCVExtractor, create_azure_client
from job_copilot_api.cv.service import get_cv_extractor
from job_copilot_api.main import app

CV_TEXT = "CV entièrement fictif, marqueur-confidentiel-test. Compétence : Python."
KEY = "fictional-secret-marker"
PROFILE = {"skills": ["Python"], "experiences": [], "education": []}


def sdk_response(
    content: object = PROFILE, *, status: str = "completed", refusal: bool = False
) -> dict[str, object]:
    message_content = (
        {"type": "refusal", "refusal": CV_TEXT + KEY}
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
        app.dependency_overrides[get_cv_extractor] = lambda: AzureCVExtractor(
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
    response = client.post("/api/v1/cv/extract", json={"cv_text": " " + CV_TEXT + " "})
    assert response.status_code == 200
    assert response.json() == PROFILE
    assert len(requests) == 1
    body = json.loads(requests[0].content)
    assert requests[0].url.path == "/openai/v1/responses"
    assert body["model"] == "gpt-4.1-mini"
    assert body["input"][1] == {"role": "user", "content": CV_TEXT}
    assert CV_TEXT not in body["input"][0]["content"]
    assert body["store"] is False
    schema = body["text"]["format"]
    assert schema["type"] == "json_schema"
    assert schema["strict"] is True
    assert schema["schema"]["additionalProperties"] is False
    assert set(schema["schema"]["required"]) == set(PROFILE)


@pytest.mark.parametrize(
    "content",
    [
        {"skills": [], "experiences": []},
        {"skills": [123], "experiences": [], "education": []},
        {**PROFILE, "extra": "unwanted"},
        None,
    ],
)
def test_invalid_structured_response(
    client: TestClient, install_sdk: Callable, content: object
) -> None:
    install_sdk(lambda request: httpx.Response(200, json=sdk_response(content)))
    response = client.post("/api/v1/cv/extract", json={"cv_text": CV_TEXT})
    assert response.status_code == 502
    assert response.json() == {
        "detail": "CV extraction provider returned an invalid response."
    }


@pytest.mark.parametrize(
    "refusal,status,detail",
    [
        (True, "completed", "CV extraction was refused by the provider."),
        (False, "incomplete", "CV extraction provider returned an invalid response."),
        (False, "failed", "CV extraction provider returned an invalid response."),
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
    response = client.post("/api/v1/cv/extract", json={"cv_text": CV_TEXT})
    assert response.status_code == 502
    assert response.json() == {"detail": detail}
    assert KEY not in response.text
    assert CV_TEXT not in response.text


@pytest.mark.parametrize(
    "failure,expected_code,expected_attempts",
    [
        ("timeout", 504, 2),
        ("connection", 503, 2),
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
            raise httpx.ReadTimeout(CV_TEXT + KEY, request=request)
        if failure == "connection":
            raise httpx.ConnectError(CV_TEXT + KEY, request=request)
        return httpx.Response(
            int(failure),
            json={"error": {"message": CV_TEXT + KEY, "type": "fictional_error"}},
            headers={"retry-after-ms": "1"},
        )

    sdk = install_sdk(handler)
    assert sdk.max_retries == 1
    response = client.post("/api/v1/cv/extract", json={"cv_text": CV_TEXT})
    assert response.status_code == expected_code
    assert len(attempts) == expected_attempts
    assert KEY not in response.text + caplog.text
    assert CV_TEXT not in response.text + caplog.text


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
    response = client.post("/api/v1/cv/extract", json={"cv_text": CV_TEXT})
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
        "job_copilot_api.cv.service.create_azure_client", lambda settings: sdk
    )
    response = client.post("/api/v1/cv/extract", json={"cv_text": CV_TEXT})
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
    response = client.post("/api/v1/cv/extract", json={"cv_text": CV_TEXT})
    assert response.status_code == 503
    assert response.json() == {"detail": "CV extraction service is not configured."}


@pytest.mark.parametrize("missing", ["AZURE_OPENAI_DEPLOYMENT", "AZURE_OPENAI_API_KEY"])
def test_partial_configuration(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://fictional.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", KEY)
    monkeypatch.delenv(missing)
    response = client.post("/api/v1/cv/extract", json={"cv_text": CV_TEXT})
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
    response = client.post("/api/v1/cv/extract", json={"cv_text": CV_TEXT})
    assert response.status_code == 502
    assert response.json() == {
        "detail": "CV extraction provider returned an invalid response."
    }
