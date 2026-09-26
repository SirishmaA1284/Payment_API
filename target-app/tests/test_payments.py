def _get_token(client) -> str:
    response = client.post("/login", json={"username": "demo", "password": "password123"})
    return response.json()["access_token"]


def _auth_headers(client) -> dict:
    return {"Authorization": f"Bearer {_get_token(client)}"}


def test_create_payment_calculates_total(client):
    response = client.post(
        "/payments",
        json={"amount": 100.0, "tax": 10.0, "discount": 5.0},
        headers=_auth_headers(client),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["total"] == 105.0


def test_create_payment_requires_auth(client):
    response = client.post("/payments", json={"amount": 100.0, "tax": 10.0, "discount": 5.0})
    assert response.status_code == 401


def test_get_payment_returns_created_payment(client):
    headers = _auth_headers(client)
    create_response = client.post(
        "/payments",
        json={"amount": 50.0, "tax": 5.0, "discount": 0.0},
        headers=headers,
    )
    payment_id = create_response.json()["id"]

    get_response = client.get(f"/payments/{payment_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["total"] == 55.0


def test_get_missing_payment_returns_404(client):
    response = client.get("/payments/999999", headers=_auth_headers(client))
    assert response.status_code == 404
