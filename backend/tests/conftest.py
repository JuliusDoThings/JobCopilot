"""Isolate tests from local credentials and reject external HTTP calls."""

from collections.abc import Iterator

import httpx
import pytest


@pytest.fixture(autouse=True)
def isolate_environment_and_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name in (
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT",
        "AZURE_OPENAI_API_KEY",
        "OPENAI_LOG",
    ):
        monkeypatch.delenv(name, raising=False)

    attempts: list[bool] = []

    def reject_network(*args: object, **kwargs: object) -> None:
        attempts.append(True)
        raise AssertionError("External HTTP is forbidden in automated tests")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", reject_network)
    monkeypatch.setattr(
        httpx.AsyncHTTPTransport, "handle_async_request", reject_network
    )
    yield
    assert not attempts, "A test attempted external HTTP"
