"""FastAPI dependencies for authn (``get_current_user``) and authz
(``require_role``).

The brief asks for three roles — Viewer / Analyst / Admin — with a strict
hierarchy: Admin > Analyst > Viewer. Higher roles satisfy lower-role
requirements automatically, which keeps route declarations terse.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.auth.security import TokenDecodeError, decode_access_token
from app.core.db import get_db
from app.models.entities import User, UserRole

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

_ROLE_ORDER: dict[UserRole, int] = {
    UserRole.viewer: 0,
    UserRole.analyst: 1,
    UserRole.admin: 2,
}


def get_current_user(
    token: str | None = Depends(_oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token)
    except TokenDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_id_raw = payload.get("sub")
    if not user_id_raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No subject claim")

    user = db.get(User, int(user_id_raw))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User missing or inactive"
        )
    return user


def require_role(minimum: UserRole):
    """Dependency factory: ``Depends(require_role(UserRole.analyst))``."""

    needed = _ROLE_ORDER[minimum]

    def _checker(current: User = Depends(get_current_user)) -> User:
        if _ROLE_ORDER[current.role] < needed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role >= {minimum.value}",
            )
        return current

    return _checker
