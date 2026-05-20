"""Auth routes: register, login, me.

Register defaults new users to the ``analyst`` role per the brief's
three-role model (Viewer / Analyst / Admin). Promotion to admin is an
out-of-band operation in v1 (direct DB write or a CLI we can add in
Phase 8) — we deliberately don't expose role assignment over HTTP.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserPublic
from app.auth.security import create_access_token, hash_password, verify_password
from app.core.db import get_db
from app.models.entities import User, UserRole

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> User:
    existing = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.analyst,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is deactivated",
        )
    token = create_access_token(user_id=user.id, role=user.role.value)
    return TokenResponse(access_token=token, role=user.role.value)


@router.get("/me", response_model=UserPublic)
def me(current: User = Depends(get_current_user)) -> User:
    return current
