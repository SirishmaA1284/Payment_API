# Payment API

A small, self-contained demo payment REST API. It exists as a controlled
target application for the **Codebase ICU** hackathon project — an
explainable, autonomous software recovery system that will later be pointed
at this repository to diagnose and (eventually) repair a regression.

This repository only contains the target application itself. It does **not**
contain any Codebase ICU dashboard, backend, agents, LLM integration, or
repair automation — those are built separately.

## Tech stack

- Python 3.11+
- FastAPI
- Uvicorn
- Pydantic
- SQLite (via the standard library `sqlite3` module)
- pytest / httpx (for the test suite)

## Project structure

```
target-app/
├── app/
│   ├── __init__.py
│   ├── main.py         # FastAPI app + route registration
│   ├── auth.py         # Token issuing/validation, /login and /profile routes
│   ├── payments.py     # /payments routes
│   ├── database.py     # SQLite connection + queries
│   └── models.py       # Pydantic request/response models
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_auth.py
│   └── test_payments.py
├── requirements.txt
├── README.md
└── .gitignore
```

## Setup

```bash
python -m venv .venv
source .venv/Scripts/activate    # on Windows Git Bash / PowerShell: .venv\Scripts\activate
pip install -r requirements.txt
```

## Running the API

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`. Interactive docs are
available at `http://127.0.0.1:8000/docs`.

A SQLite database file (`payments.db`) is created automatically on startup
in the project root.

## Running tests

```bash
pytest -q
```

Each test run uses an isolated, temporary SQLite database so tests do not
interfere with each other or with `payments.db`.

## API endpoints

| Method | Path                | Auth required | Description                          |
|--------|---------------------|----------------|--------------------------------------|
| GET    | `/`                 | No             | Health check                         |
| POST   | `/login`             | No             | Exchange demo credentials for a token |
| GET    | `/profile`           | Yes            | Return the demo user's profile       |
| POST   | `/payments`          | Yes            | Create a payment, returns the total  |
| GET    | `/payments/{id}`     | Yes            | Retrieve a stored payment            |

### Authentication

Demo credentials:

```json
{ "username": "demo", "password": "password123" }
```

`POST /login` returns a bearer token to send as `Authorization: Bearer <token>`
on subsequent requests.

Tokens are deterministic and self-contained (no server-side session store),
suitable only for this local demo — they are **not** a production-grade auth
scheme.

### Payments

`POST /payments` accepts:

```json
{ "amount": 100.0, "tax": 10.0, "discount": 5.0 }
```

The total is calculated as:

```
total = amount + tax - discount
```

## Expected behavior

- A valid token allows the request to proceed.
- A syntactically invalid or tampered token results in `401 Unauthorized`.
- An expired token is intended to result in `401 Unauthorized`.
- Requesting a payment ID that does not exist returns `404 Not Found`.

## ⚠️ Known state: intentional regression

This repository's current state contains **one intentionally introduced
regression** in the authentication error-handling path, added on top of an
otherwise fully working and tested application. It was introduced for the
**Codebase ICU** hackathon demonstration, so that an autonomous agent can
practice locating and explaining a real regression using the test suite,
source code, and Git history.

Running `pytest -q` on the current `main` branch will show at least one
failing test related to expired-token handling. The root cause is **not**
documented here on purpose — it is meant to be discovered by inspecting the
failing test, the authentication code, the relevant Git history, and the
exception path, not by reading this file.

Do not "fix" this regression as part of unrelated work on this repository;
it is left in place deliberately for the Codebase ICU demo.
