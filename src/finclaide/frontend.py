from __future__ import annotations

import httpx
from flask import Flask, Response, abort, current_app, request

# Headers that hop-by-hop must not be forwarded through a proxy.
HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "content-length",
        "content-encoding",
    }
)

FALLBACK_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Finclaide</title>
  </head>
  <body>
    <main style="font-family: system-ui, sans-serif; max-width: 32rem; margin: 4rem auto; padding: 1rem;">
      <h1>Finclaide</h1>
      <p>The frontend container is not reachable. Set <code>FINCLAIDE_FRONTEND_URL</code> on the
      Flask service to the SvelteKit container's internal URL (e.g. <code>http://web:3000</code>).</p>
    </main>
  </body>
</html>
"""


def register_frontend(app: Flask) -> None:
    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def serve_frontend(path: str):
        if _is_api_path(path):
            abort(404)
        config = current_app.config["FINCLAIDE_CONFIG"]
        target = getattr(config, "frontend_url", None)
        if not target:
            return Response(FALLBACK_HTML, mimetype="text/html")
        return _proxy_to_frontend(target, path)


def _is_api_path(path: str) -> bool:
    if path.startswith(("api/", "ui-api/", "healthz")):
        return True
    return path in {"api", "ui-api"}


def _proxy_to_frontend(target_base: str, path: str) -> Response:
    upstream = f"{target_base.rstrip('/')}/{path}"
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in HOP_BY_HOP
    }
    # Keep proxy responses byte-for-byte usable after Flask strips
    # Content-Encoding. Browser requests can advertise zstd, which httpx does
    # not always decode before we return upstream_response.content.
    headers["Accept-Encoding"] = "identity"
    headers.setdefault("X-Forwarded-Host", request.host)
    headers.setdefault("X-Forwarded-Proto", request.scheme)
    if "X-Forwarded-For" not in headers and request.remote_addr:
        headers["X-Forwarded-For"] = request.remote_addr

    try:
        upstream_response = httpx.request(
            method=request.method,
            url=upstream,
            params=request.args,
            content=request.get_data(),
            headers=headers,
            follow_redirects=False,
            timeout=30.0,
        )
    except httpx.HTTPError as error:
        return Response(
            f"Frontend container unreachable: {error}",
            status=502,
            mimetype="text/plain",
        )

    response_headers = [
        (key, value)
        for key, value in upstream_response.headers.items()
        if key.lower() not in HOP_BY_HOP
    ]
    return Response(
        upstream_response.content,
        status=upstream_response.status_code,
        headers=response_headers,
    )
