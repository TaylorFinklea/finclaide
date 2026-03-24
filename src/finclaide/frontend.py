from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, Response, abort, current_app, request, send_from_directory


FRONTEND_FALLBACK_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    {runtime_head}
    <title>Finclaide</title>
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>
"""


def _default_frontend_dist() -> Path:
    return Path(__file__).resolve().parents[2] / "frontend" / "dist"


def register_frontend(app: Flask) -> None:
    dist_dir = current_frontend_dist(app)

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def serve_frontend(path: str):
        if path.startswith(("api/", "ui-api/", "healthz")):
            abort(404)
        if path in {"api", "ui-api"}:
            abort(404)
        if dist_dir.exists():
            requested = dist_dir / path
            if path and requested.is_file():
                return send_from_directory(dist_dir, path)
            return Response(_render_index_html(dist_dir / "index.html"), mimetype="text/html")
        return Response(_fallback_html(), mimetype="text/html")


def current_frontend_dist(app: Flask) -> Path:
    config = app.config["FINCLAIDE_CONFIG"]
    if config.frontend_dist is None:
        return _default_frontend_dist()
    if config.frontend_dist.is_absolute():
        return config.frontend_dist
    return (Path.cwd() / config.frontend_dist).resolve()


def _fallback_html() -> str:
    return FRONTEND_FALLBACK_HTML.format(runtime_head=_runtime_head())


def _render_index_html(index_path: Path) -> str:
    index_html = index_path.read_text()
    runtime_head = _runtime_head()
    if "</head>" in index_html:
        return index_html.replace("</head>", f"{runtime_head}\n  </head>", 1)
    return f"{runtime_head}\n{index_html}"


def _runtime_head() -> str:
    base_path = _frontend_base_path()
    encoded_base_path = json.dumps(base_path)
    href = "/" if not base_path else f"{base_path}/"
    encoded_href = json.dumps(href)
    return (
        f"<script>window.__FINCLAIDE_BASE_PATH__ = {encoded_base_path};"
        f"window.__FINCLAIDE_BASE_HREF__ = {encoded_href};</script>\n"
        f'    <base href="{href}">'
    )


def _frontend_base_path() -> str:
    ingress_path = request.headers.get("X-Ingress-Path", "").rstrip("/")
    forwarded_prefix = request.headers.get("X-Forwarded-Prefix", "").rstrip("/")
    base_path = ingress_path or forwarded_prefix
    if not base_path or base_path == "/":
        return ""
    if not base_path.startswith("/"):
        return f"/{base_path}"
    return base_path
