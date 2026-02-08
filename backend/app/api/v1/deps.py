"""
Auth dependencies for FastAPI endpoints
"""
from typing import Optional

from fastapi import Depends, HTTPException, Request, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError

from app.database.connection import get_db
from app.models.user import User
from app.services.auth.auth_service import decode_token

bearer_scheme = HTTPBearer()
optional_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Extract user from Authorization: Bearer header."""
    token = credentials.credentials
    return _resolve_user(token, db)


def get_current_user_from_query(
    token: str = Query(..., description="JWT auth token"),
    db: Session = Depends(get_db),
) -> User:
    """Extract user from ?token= query param (for SSE/EventSource)."""
    return _resolve_user(token, db)


def get_optional_user_from_query(
    token: Optional[str] = Query(None, description="JWT auth token"),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Extract user from ?token= query param. Returns None if missing/invalid."""
    if not token:
        return None
    return _resolve_user_optional(token, db)


def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Extract user from Bearer header. Returns None if missing/invalid."""
    if not credentials:
        return None
    return _resolve_user_optional(credentials.credentials, db)


def _resolve_user(token: str, db: Session) -> User:
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def _resolve_user_optional(token: str, db: Session) -> Optional[User]:
    """Try to resolve a user from a token. Returns None on any failure."""
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None
    except (JWTError, Exception):
        return None

    return db.query(User).filter(User.id == user_id).first()
