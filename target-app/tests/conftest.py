import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    db_path = tmp_path / f"test_{uuid.uuid4().hex}.db"
    monkeypatch.setenv("PAYMENTS_DB_PATH", str(db_path))
    yield


@pytest.fixture()
def client():
    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
