from app.core.config import Settings


def test_register_returns_token(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "user@example.com", "password": "secret123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["email"] == "user@example.com"
    assert data["user"]["is_admin"] is False
    assert data["access_token"]


def test_login_returns_token_for_existing_user(client):
    client.post(
        "/api/auth/register",
        json={"email": "login-user@example.com", "password": "secret123"},
    )

    response = client.post(
        "/api/auth/login",
        json={"email": "login-user@example.com", "password": "secret123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["user"]["email"] == "login-user@example.com"
    assert data["user"]["is_admin"] is False
    assert data["access_token"]


def test_login_rejects_invalid_password(client):
    client.post(
        "/api/auth/register",
        json={"email": "login-fail@example.com", "password": "secret123"},
    )

    response = client.post(
        "/api/auth/login",
        json={"email": "login-fail@example.com", "password": "wrongpass"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


def test_login_rejects_short_invalid_password_with_401(client):
    client.post(
        "/api/auth/register",
        json={"email": "short-login-fail@example.com", "password": "secret123"},
    )

    response = client.post(
        "/api/auth/login",
        json={"email": "short-login-fail@example.com", "password": "short"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


def test_me_requires_auth(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_me_returns_current_user_with_bearer_token(client):
    register_response = client.post(
        "/api/auth/register",
        json={"email": "user2@example.com", "password": "secret123"},
    )
    access_token = register_response.json()["access_token"]

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "user2@example.com"
    assert response.json()["is_admin"] is False


def test_register_login_me_return_is_admin_for_whitelisted_email(client, monkeypatch):
    import app.api.routes.auth as auth_routes

    monkeypatch.setattr(
        auth_routes,
        "settings",
        Settings(admin_emails=("admin@example.com",)),
    )

    register_response = client.post(
        "/api/auth/register",
        json={"email": "Admin@Example.com", "password": "secret123"},
    )
    assert register_response.status_code == 200
    register_data = register_response.json()
    assert register_data["user"]["is_admin"] is True

    login_response = client.post(
        "/api/auth/login",
        json={"email": "Admin@Example.com", "password": "secret123"},
    )
    assert login_response.status_code == 200
    login_data = login_response.json()
    assert login_data["user"]["is_admin"] is True

    access_token = register_data["access_token"]
    me_response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["is_admin"] is True


def test_openapi_uses_http_bearer_without_login_token_url(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    security_schemes = response.json()["components"]["securitySchemes"]
    assert security_schemes == {
        "HTTPBearer": {"type": "http", "scheme": "bearer"}
    }
