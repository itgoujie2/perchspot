"""
Auth API endpoints - register, login, me
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.user import User
from app.services.auth.auth_service import hash_password, verify_password, create_access_token
from app.api.v1.deps import get_current_user
from app.services.promotions.referral_service import register_referral

logger = logging.getLogger(__name__)

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    referral_code: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    user_id: str
    email: str
    credit_balance: float
    token: str


class MeResponse(BaseModel):
    user_id: str
    email: str
    credit_balance: float


@router.post("/register", response_model=AuthResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    if len(req.password) < 6:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password must be at least 6 characters")

    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Process referral code if provided
    if req.referral_code:
        if register_referral(db, req.referral_code, user.id):
            logger.info(f"User {user.email} registered with referral code {req.referral_code}")
        else:
            logger.warning(f"Invalid or already used referral code: {req.referral_code}")

    token = create_access_token(user.id, user.email)
    logger.info(f"User registered: {user.email}")

    return AuthResponse(
        user_id=user.id,
        email=user.email,
        credit_balance=float(user.credit_balance),
        token=token,
    )


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token = create_access_token(user.id, user.email)
    logger.info(f"User logged in: {user.email}")

    return AuthResponse(
        user_id=user.id,
        email=user.email,
        credit_balance=float(user.credit_balance),
        token=token,
    )


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)):
    return MeResponse(
        user_id=user.id,
        email=user.email,
        credit_balance=float(user.credit_balance),
    )
