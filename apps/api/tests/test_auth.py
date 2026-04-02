def test_register_returns_token(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "user@example.com", "password": "secret123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["email"] == "user@example.com"
    assert data["access_token"]


def test_me_requires_auth(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
