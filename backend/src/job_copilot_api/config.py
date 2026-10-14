"""Server configuration; environment files are never loaded implicitly."""

import os
import re
from dataclasses import dataclass, field

AZURE_ENDPOINT = re.compile(
    r"https://[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"\.openai\.azure\.com(?::443)?(?:/openai/v1)?/?",
    re.ASCII,
)


@dataclass(frozen=True)
class AzureSettings:
    endpoint: str
    deployment: str
    api_key: str = field(repr=False)

    def __post_init__(self) -> None:
        if not AZURE_ENDPOINT.fullmatch(self.endpoint):
            raise ValueError("Azure OpenAI endpoint is not allowed.")

    @classmethod
    def from_environment(cls) -> "AzureSettings | None":
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip()
        deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "").strip()
        api_key = os.environ.get("AZURE_OPENAI_API_KEY", "").strip()
        if not deployment or not api_key:
            return None
        try:
            return cls(endpoint=endpoint, deployment=deployment, api_key=api_key)
        except ValueError:
            return None

    @property
    def base_url(self) -> str:
        endpoint = self.endpoint.rstrip("/")
        if endpoint.endswith("/openai/v1"):
            return endpoint + "/"
        return endpoint + "/openai/v1/"
