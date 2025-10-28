"""Simple token-based auth helpers for i4g API (MVP)."""

from fastapi import HTTPException, Header, status
from typing import Optional

# Minimal token -> user mapping for prototype.
# In production, use a proper identity provider.
_API_TOKENS = {
    # token: {"username": "alice", "role": "analyst"}
    "dev-analyst-token": {"username": "analyst_1", "role": "analyst"},
    "dev-admin-token": {"username": "admin", "role": "admin"},
}


def require_token(x_api_key: Optional[str] = Header(None)):
    """Validate API key header and return user info.

    Args:
        x_api_key: Value of the `X-API-KEY` header.

    Returns:
        dict: user info with 'username' and 'role'.

    Raises:
        HTTPException: 401 if missing/invalid.
    """
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-KEY")
    user = _API_TOKENS.get(x_api_key)
    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")
    return user


def require_role(required_role: str):
    """Dependency factory to enforce a required role."""

    def _checker(user= require_token):
        # Note: FastAPI will resolve require_token first and pass value here
        if isinstance(user, dict):
            role = user.get("role")
            if role == required_role or role == "admin":
                return user
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    return _checker
