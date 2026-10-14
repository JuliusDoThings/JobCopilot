"""Server configuration; environment files are never loaded implicitly."""

import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit


@dataclass(frozen=True)
class AzureSettings:
    endpoint: str
    deployment: str
    api_key: str = field(repr=False)

    @classmethod
    def from_environment(cls) -> "AzureSettings | None":
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/")
        deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "").strip()
        api_key = os.environ.get("AZURE_OPENAI_API_KEY", "").strip()
        try:
            url = urlsplit(endpoint)
            url.port  # Validate malformed or out-of-range ports too.
        except ValueError:
            return None
        if (
            not endpoint
            or not deployment
            or not api_key
            or url.scheme != "https"
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.path not in ("", "/openai/v1")
        ):
            return None
        return cls(endpoint=endpoint, deployment=deployment, api_key=api_key)

    @property
    def base_url(self) -> str:
        if self.endpoint.endswith("/openai/v1"):
            return self.endpoint + "/"
        return self.endpoint + "/openai/v1/"
