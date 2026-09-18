"""Conforming FastAPI application complying with all Vibe Guard rules."""

import hmac
import os
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPBearer

app = FastAPI()
security = HTTPBearer()


def get_current_user(token: str = Depends(security)) -> str:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )
    return "authorized_user"


@app.post("/admin/protected", dependencies=[Depends(get_current_user)])
def safe_admin_action(payload: dict):
    return {"status": "ok", "payload": payload}


def verify_secret_hash(stored_hash: bytes, provided_hash: bytes) -> bool:
    """Safe constant-time digest comparison."""
    return hmac.compare_digest(stored_hash, provided_hash)


def get_environment_config() -> str:
    """Reads configuration safely from runtime environment without committed .env file."""
    return os.environ.get("SERVICE_NAME", "default-service")
