from __future__ import annotations

import os
from dataclasses import dataclass, replace
from typing import Any
from urllib.parse import urlparse

from dotenv import find_dotenv, load_dotenv


def _default_health_url(api_base_url: str) -> str:
    parsed = urlparse(api_base_url)
    path = parsed.path.rstrip("/")
    if path.endswith("/api"):
        path = path[:-4] or "/"
    if not path.endswith("/healthz"):
        path = path.rstrip("/") + "/healthz"
    return parsed._replace(path=path, params="", query="", fragment="").geturl()


@dataclass(frozen=True)
class MCPConfig:
    api_base_url: str
    api_token: str | None
    health_url: str

    @classmethod
    def from_env(cls, overrides: dict[str, Any] | None = None) -> "MCPConfig":
        dotenv_path = find_dotenv(usecwd=True)
        if dotenv_path:
            load_dotenv(dotenv_path, override=False)
        api_base_url = os.getenv("FINCLAIDE_API_BASE_URL", "http://127.0.0.1:8050/api").rstrip("/")
        config = cls(
            api_base_url=api_base_url,
            api_token=os.getenv("FINCLAIDE_API_TOKEN"),
            health_url=os.getenv("FINCLAIDE_HEALTH_URL", _default_health_url(api_base_url)),
        )
        if not overrides:
            return config
        return replace(config, **overrides)
