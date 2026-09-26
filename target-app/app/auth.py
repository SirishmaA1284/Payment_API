import base64
import hashlib
import hmac
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.models import LoginRequest, LoginResponse, ProfileResponse

logger = logging.getLogger(__name__)

SECRET_KEY = "demo-secret-key-not-for-production"
TOKEN_TTL_SECONDS = 3600

DEMO_USER = {
    "username": "demo",
    "password": "password123",
    "display_name": "Demo User",
}


class InvalidTokenError(Exception):
    pass


class ExpiredTokenError(Exception):
    pass


def _sign(payload: str) -> str:
    return hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()


def create_token(username: str, issued_at: Optional[float] = None) -> str:
    if issued_at is None:
        issued_at = time.time()
    payload = f"{username}:{issued_at}"
    signature = _sign(payload)
    raw = f"{payload}:{signature}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_token(token: str) -> str:
    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        username, issued_at_str, signature = raw.rsplit(":", 2)
    except (ValueError, UnicodeDecodeError) as exc:
        raise InvalidTokenError("Malformed token") from exc

    expected_signature = _sign(f"{username}:{issued_at_str}")
    if not hmac.compare_digest(signature, expected_signature):
        raise InvalidTokenError("Invalid token signature")

    if username != DEMO_USER["username"]:
        raise InvalidTokenError("Unknown user")

    if time.time() - float(issued_at_str) > TOKEN_TTL_SECONDS:
        raise ExpiredTokenError("Token has expired")

    return username


def authenticate(username: str, password: str) -> Optional[str]:
    if username == DEMO_USER["username"] and password == DEMO_USER["password"]:
        return create_token(username)
    return None


def get_current_user(authorization: str = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
        )

    token = authorization.removeprefix("Bearer ")

    try:
        return decode_token(token)
    except ExpiredTokenError as exc:
        logger.info("Rejected expired token (age=%.0fs)", time.time() - issued_at)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        ) from exc
    except InvalidTokenError as exc:
        logger.info("Rejected invalid token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from exc


router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(credentials: LoginRequest) -> LoginResponse:
    token = authenticate(credentials.username, credentials.password)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    return LoginResponse(access_token=token)


@router.get("/profile", response_model=ProfileResponse)
def profile(username: str = Depends(get_current_user)) -> ProfileResponse:
    return ProfileResponse(username=username, display_name=DEMO_USER["display_name"])
