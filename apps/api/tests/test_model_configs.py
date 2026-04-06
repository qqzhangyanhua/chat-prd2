from app.core.config import Settings


def _login_with_email(client, email: str) -> str:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "secret123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _set_admin_whitelist(monkeypatch) -> None:
    import app.api.routes.admin_model_configs as admin_model_configs_routes

    monkeypatch.setattr(
        admin_model_configs_routes,
        "settings",
        Settings(admin_emails=("admin@example.com",)),
    )


def test_enabled_model_configs_returns_enabled_only_and_hides_api_key(client, monkeypatch):
    _set_admin_whitelist(monkeypatch)
    admin_token = _login_with_email(client, "admin@example.com")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    create_disabled = client.post(
        "/api/admin/model-configs",
        headers=admin_headers,
        json={
            "name": "禁用模型",
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-disabled",
            "model": "gpt-4.1-mini",
            "enabled": False,
        },
    )
    assert create_disabled.status_code == 200

    create_enabled = client.post(
        "/api/admin/model-configs",
        headers=admin_headers,
        json={
            "name": "启用模型",
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-enabled",
            "model": "gpt-4.1",
            "enabled": True,
        },
    )
    assert create_enabled.status_code == 200

    user_token = _login_with_email(client, "normal-user@example.com")
    user_headers = {"Authorization": f"Bearer {user_token}"}
    enabled_response = client.get("/api/model-configs/enabled", headers=user_headers)

    assert enabled_response.status_code == 200
    data = enabled_response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "启用模型"
    assert "api_key" not in data["items"][0]


def test_non_admin_cannot_create_update_delete_model_configs(client):
    user_token = _login_with_email(client, "user@example.com")
    user_headers = {"Authorization": f"Bearer {user_token}"}

    create_response = client.post(
        "/api/admin/model-configs",
        headers=user_headers,
        json={
            "name": "OpenAI",
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-secret",
            "model": "gpt-4.1-mini",
            "enabled": True,
        },
    )
    assert create_response.status_code == 403

    patch_response = client.patch(
        "/api/admin/model-configs/nonexistent",
        headers=user_headers,
        json={"enabled": False},
    )
    assert patch_response.status_code == 403

    delete_response = client.delete(
        "/api/admin/model-configs/nonexistent",
        headers=user_headers,
    )
    assert delete_response.status_code == 403


def test_admin_can_crud_model_configs_and_enabled_endpoint_hides_api_key(client, monkeypatch):
    _set_admin_whitelist(monkeypatch)
    admin_token = _login_with_email(client, "Admin@example.com")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    create_response = client.post(
        "/api/admin/model-configs",
        headers=admin_headers,
        json={
            "name": "OpenAI 主配置",
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-secret",
            "model": "gpt-4.1",
            "enabled": True,
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    config_id = created["id"]
    assert created["api_key"] == "sk-secret"

    list_response = client.get("/api/admin/model-configs", headers=admin_headers)
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert len(list_data["items"]) == 1
    assert list_data["items"][0]["id"] == config_id

    update_response = client.patch(
        f"/api/admin/model-configs/{config_id}",
        headers=admin_headers,
        json={
            "model": "gpt-4.1-mini",
            "enabled": False,
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["model"] == "gpt-4.1-mini"
    assert updated["enabled"] is False

    enabled_response = client.get(
        "/api/model-configs/enabled",
        headers=admin_headers,
    )
    assert enabled_response.status_code == 200
    assert enabled_response.json() == {"items": []}

    client.patch(
        f"/api/admin/model-configs/{config_id}",
        headers=admin_headers,
        json={"enabled": True},
    )

    enabled_response = client.get(
        "/api/model-configs/enabled",
        headers=admin_headers,
    )
    assert enabled_response.status_code == 200
    enabled_data = enabled_response.json()
    assert len(enabled_data["items"]) == 1
    assert enabled_data["items"][0]["id"] == config_id
    assert "api_key" not in enabled_data["items"][0]

    delete_response = client.delete(
        f"/api/admin/model-configs/{config_id}",
        headers=admin_headers,
    )
    assert delete_response.status_code == 204

    after_delete_response = client.get("/api/admin/model-configs", headers=admin_headers)
    assert after_delete_response.status_code == 200
    assert after_delete_response.json() == {"items": []}
