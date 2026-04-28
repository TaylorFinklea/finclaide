from __future__ import annotations


def _seed_active_plan(app):
    """Bootstrap an active plan in the test database via the API
    importer. Returns a same-origin test client (no Origin header so
    require_same_origin treats it as same-origin)."""
    client = app.test_client()
    response = client.post(
        "/api/budget/import",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200, response.get_json()
    return client


def _create_sandbox(client, ui_headers, from_plan_id):
    response = client.post(
        "/ui-api/scenarios",
        json={"from_plan_id": from_plan_id},
        headers=ui_headers,
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()["plan"]["id"]


def _active_plan_id(client, ui_headers):
    response = client.get("/ui-api/plan/active", headers=ui_headers)
    assert response.status_code == 200, response.get_json()
    return response.get_json()["plan"]["id"]


def test_save_endpoint_round_trip(app_factory, ui_headers):
    app = app_factory()
    client = _seed_active_plan(app)
    active_id = _active_plan_id(client, ui_headers)
    sandbox_id = _create_sandbox(client, ui_headers, active_id)

    response = client.post(
        f"/ui-api/scenarios/{sandbox_id}/save",
        json={"label": "Summer budget"},
        headers=ui_headers,
    )
    assert response.status_code == 200, response.get_json()
    payload = response.get_json()
    # Save endpoint envelopes the active-plan response in {"plan": ...},
    # matching commit's shape; the inner plan wrapper holds id/label.
    assert payload["plan"]["plan"]["id"] == sandbox_id
    assert payload["plan"]["plan"]["label"] == "Summer budget"


def test_save_endpoint_rejects_blank_label_400(app_factory, ui_headers):
    app = app_factory()
    client = _seed_active_plan(app)
    active_id = _active_plan_id(client, ui_headers)
    sandbox_id = _create_sandbox(client, ui_headers, active_id)

    response = client.post(
        f"/ui-api/scenarios/{sandbox_id}/save",
        json={"label": "   "},
        headers=ui_headers,
    )
    assert response.status_code == 400


def test_save_endpoint_missing_label_field_400(app_factory, ui_headers):
    app = app_factory()
    client = _seed_active_plan(app)
    active_id = _active_plan_id(client, ui_headers)
    sandbox_id = _create_sandbox(client, ui_headers, active_id)

    response = client.post(
        f"/ui-api/scenarios/{sandbox_id}/save",
        json={},
        headers=ui_headers,
    )
    assert response.status_code == 400


def test_save_endpoint_rejects_duplicate_label_400(app_factory, ui_headers):
    app = app_factory()
    client = _seed_active_plan(app)
    active_id = _active_plan_id(client, ui_headers)

    saved_response = client.post(
        "/ui-api/scenarios",
        json={"from_plan_id": active_id, "label": "Summer budget"},
        headers=ui_headers,
    )
    assert saved_response.status_code == 201
    sandbox_id = _create_sandbox(client, ui_headers, active_id)

    response = client.post(
        f"/ui-api/scenarios/{sandbox_id}/save",
        json={"label": "Summer budget"},
        headers=ui_headers,
    )
    assert response.status_code == 400
    body = response.get_json()
    detail = body.get("error_detail") or {}
    haystack = (detail.get("message") or "") + " " + (body.get("error") or "")
    assert "Summer budget" in haystack


def test_save_endpoint_requires_ui_header(app_factory):
    app = app_factory()
    client = _seed_active_plan(app)
    response = client.post(
        "/ui-api/scenarios/1/save",
        json={"label": "X"},
    )
    assert response.status_code == 403


def test_fork_endpoint_returns_201(app_factory, ui_headers):
    app = app_factory()
    client = _seed_active_plan(app)
    active_id = _active_plan_id(client, ui_headers)
    saved_response = client.post(
        "/ui-api/scenarios",
        json={"from_plan_id": active_id, "label": "Summer budget"},
        headers=ui_headers,
    )
    assert saved_response.status_code == 201
    saved_id = saved_response.get_json()["plan"]["id"]

    response = client.post(
        f"/ui-api/scenarios/{saved_id}/fork",
        json={},
        headers=ui_headers,
    )
    assert response.status_code == 201, response.get_json()
    payload = response.get_json()
    assert payload["plan"]["id"] != saved_id
    assert payload["plan"]["status"] == "scenario"
    assert payload["plan"]["label"] is None


def test_fork_endpoint_404_when_not_saved(app_factory, ui_headers):
    app = app_factory()
    client = _seed_active_plan(app)
    active_id = _active_plan_id(client, ui_headers)
    sandbox_id = _create_sandbox(client, ui_headers, active_id)

    response = client.post(
        f"/ui-api/scenarios/{sandbox_id}/fork",
        json={},
        headers=ui_headers,
    )
    assert response.status_code == 404
