"""
Favorites API endpoints - save/list/delete favorite properties
"""
import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.user import User
from app.models.favorite import UserFavorite
from app.api.v1.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


class AddFavoriteRequest(BaseModel):
    address: str
    nickname: Optional[str] = None
    notes: Optional[str] = None


class UpdateFavoriteRequest(BaseModel):
    nickname: Optional[str] = None
    notes: Optional[str] = None


class FavoriteResponse(BaseModel):
    id: str
    address: str
    nickname: Optional[str]
    notes: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class FavoritesListResponse(BaseModel):
    favorites: List[FavoriteResponse]
    total: int


@router.get("", response_model=FavoritesListResponse)
def list_favorites(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all user's favorite properties"""
    favorites = (
        db.query(UserFavorite)
        .filter(UserFavorite.user_id == user.id)
        .order_by(UserFavorite.created_at.desc())
        .all()
    )

    return FavoritesListResponse(
        favorites=[
            FavoriteResponse(
                id=f.id,
                address=f.address,
                nickname=f.nickname,
                notes=f.notes,
                created_at=f.created_at.isoformat() if f.created_at else "",
            )
            for f in favorites
        ],
        total=len(favorites),
    )


@router.post("", response_model=FavoriteResponse, status_code=status.HTTP_201_CREATED)
def add_favorite(
    req: AddFavoriteRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a property to favorites"""
    # Check if already favorited
    existing = (
        db.query(UserFavorite)
        .filter(UserFavorite.user_id == user.id, UserFavorite.address == req.address)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Property already in favorites"
        )

    favorite = UserFavorite(
        user_id=user.id,
        address=req.address,
        nickname=req.nickname,
        notes=req.notes,
    )
    db.add(favorite)
    db.commit()
    db.refresh(favorite)

    logger.info(f"User {user.email} added favorite: {req.address}")

    return FavoriteResponse(
        id=favorite.id,
        address=favorite.address,
        nickname=favorite.nickname,
        notes=favorite.notes,
        created_at=favorite.created_at.isoformat() if favorite.created_at else "",
    )


@router.get("/check")
def check_favorite(
    address: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check if an address is in user's favorites"""
    existing = (
        db.query(UserFavorite)
        .filter(UserFavorite.user_id == user.id, UserFavorite.address == address)
        .first()
    )
    return {"is_favorite": existing is not None, "favorite_id": existing.id if existing else None}


@router.patch("/{favorite_id}", response_model=FavoriteResponse)
def update_favorite(
    favorite_id: str,
    req: UpdateFavoriteRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a favorite's nickname or notes"""
    favorite = (
        db.query(UserFavorite)
        .filter(UserFavorite.id == favorite_id, UserFavorite.user_id == user.id)
        .first()
    )
    if not favorite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Favorite not found")

    if req.nickname is not None:
        favorite.nickname = req.nickname
    if req.notes is not None:
        favorite.notes = req.notes

    db.commit()
    db.refresh(favorite)

    return FavoriteResponse(
        id=favorite.id,
        address=favorite.address,
        nickname=favorite.nickname,
        notes=favorite.notes,
        created_at=favorite.created_at.isoformat() if favorite.created_at else "",
    )


@router.delete("/{favorite_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_favorite(
    favorite_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a property from favorites"""
    favorite = (
        db.query(UserFavorite)
        .filter(UserFavorite.id == favorite_id, UserFavorite.user_id == user.id)
        .first()
    )
    if not favorite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Favorite not found")

    db.delete(favorite)
    db.commit()

    logger.info(f"User {user.email} removed favorite: {favorite.address}")
    return None
