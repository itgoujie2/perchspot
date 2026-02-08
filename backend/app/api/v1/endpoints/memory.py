"""
Memory API endpoints - View and manage user memories
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.services.memory.memory_service import MemoryService

logger = logging.getLogger(__name__)

router = APIRouter()


class MemoryResponse(BaseModel):
    """Individual memory item"""
    id: str
    category: str
    key: str
    value: str
    confidence: str
    source: str
    created_at: Optional[str]
    updated_at: Optional[str]


class CityActivityResponse(BaseModel):
    """Individual city activity item"""
    id: str
    city: str
    state: str
    region: Optional[str]
    activity_count: int
    last_activity: Optional[str]


class AllMemoriesResponse(BaseModel):
    """Response containing all user memories and city activities"""
    memories: list[MemoryResponse]
    city_activities: list[CityActivityResponse]


class DeleteResponse(BaseModel):
    """Response for delete operations"""
    success: bool
    deleted_count: Optional[int] = None


@router.get("/memories", response_model=AllMemoriesResponse)
async def get_user_memories(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all memories and city activities for the authenticated user.
    """
    memory_service = MemoryService(db)
    data = memory_service.get_all_user_data(user.id)
    return AllMemoriesResponse(
        memories=[MemoryResponse(**m) for m in data["memories"]],
        city_activities=[CityActivityResponse(**c) for c in data["city_activities"]],
    )


@router.delete("/memories/{memory_id}", response_model=DeleteResponse)
async def delete_memory(
    memory_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a specific memory by ID.
    User can only delete their own memories.
    """
    memory_service = MemoryService(db)
    success = memory_service.delete_memory(user.id, memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")
    return DeleteResponse(success=True)


@router.delete("/memories", response_model=DeleteResponse)
async def delete_all_memories(
    include_cities: bool = Query(False, description="Also delete city activity history"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete all memories for the authenticated user (privacy reset).
    Optionally include city activity history.
    """
    memory_service = MemoryService(db)
    memory_count = memory_service.delete_all_memories(user.id)
    city_count = 0
    if include_cities:
        city_count = memory_service.delete_all_city_activities(user.id)
    return DeleteResponse(success=True, deleted_count=memory_count + city_count)


@router.delete("/city-activities/{activity_id}", response_model=DeleteResponse)
async def delete_city_activity(
    activity_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a specific city activity by ID.
    """
    memory_service = MemoryService(db)
    success = memory_service.delete_city_activity(user.id, activity_id)
    if not success:
        raise HTTPException(status_code=404, detail="City activity not found")
    return DeleteResponse(success=True)
