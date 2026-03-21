from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import Response, current_app, jsonify, request

from finclaide.errors import ConfigError


def require_bearer_token(handler: Callable[..., Response]):
    @wraps(handler)
    def wrapped(*args: Any, **kwargs: Any):
        config = current_app.config["FINCLAIDE_CONFIG"]
        if not config.api_token:
            raise ConfigError("FINCLAIDE_API_TOKEN must be configured before using the API.")
        header_value = request.headers.get("Authorization", "")
        expected = f"Bearer {config.api_token}"
        if header_value != expected:
            return jsonify({"error": "unauthorized"}), 401
        return handler(*args, **kwargs)

    return wrapped
