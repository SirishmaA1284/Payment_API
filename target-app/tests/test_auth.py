from app.auth import create_token


def test_login_success(client):
    response = client.post("/login", json={"username": "demo", "password": "password123"})
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_invalid_credentials(client):
    response = client.post("/login", json={"username": "demo", "password": "wrong"})
    assert response.status_code == 401


def test_profile_with_valid_token(client):
    login_response = client.post("/login", json={"username": "demo", "password": "password123"})
    token = login_response.json()["access_token"]

    response = client.get("/profile", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["username"] == "demo"


def test_profile_without_token(client):
    response = client.get("/profile")
    assert response.status_code == 401


def test_profile_with_invalid_token(client):
    response = client.get("/profile", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_profile_with_expired_token(client):
    expired_token = create_token("demo", issued_at=0)
    response = client.get("/profile", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401
