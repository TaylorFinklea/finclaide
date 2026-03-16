from __future__ import annotations

from pathlib import Path

from flask import Flask, Response, abort, current_app, send_from_directory


FRONTEND_FALLBACK_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
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
            return send_from_directory(dist_dir, "index.html")
        return Response(FRONTEND_FALLBACK_HTML, mimetype="text/html")


def current_frontend_dist(app: Flask) -> Path:
    config = app.config["FINCLAIDE_CONFIG"]
    return config.frontend_dist or _default_frontend_dist()
