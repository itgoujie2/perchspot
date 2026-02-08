"""
Memory Service - CRUD operations and context formatting for user memories
"""
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime

from app.models.memory import UserMemory, UserCityActivity

logger = logging.getLogger(__name__)

# Category display order and labels
CATEGORY_ORDER = ["budget", "property_preference", "intent", "family_situation", "lifestyle"]
CATEGORY_LABELS = {
    "budget": "Budget",
    "property_preference": "Property Preferences",
    "intent": "Goals",
    "family_situation": "Family",
    "lifestyle": "Lifestyle",
}


class MemoryService:
    """Service for managing user memories and city activity"""

    def __init__(self, db: Session):
        self.db = db

    def save_memory(
        self,
        user_id: str,
        category: str,
        memory_key: str,
        memory_value: str,
        confidence: str = "medium",
        source: str = "chat",
        source_context: Optional[str] = None,
    ) -> UserMemory:
        """
        Save or update a user memory.
        Uses UPSERT to update existing memories with same category+key.
        """
        # Check if memory exists
        existing = self.db.query(UserMemory).filter(
            UserMemory.user_id == user_id,
            UserMemory.category == category,
            UserMemory.memory_key == memory_key,
        ).first()

        if existing:
            # Update existing memory
            existing.memory_value = memory_value
            existing.confidence = confidence
            existing.source = source
            existing.source_context = source_context
            existing.updated_at = datetime.utcnow()
            self.db.commit()
            logger.info(f"Updated memory: {category}/{memory_key} for user {user_id}")
            return existing
        else:
            # Create new memory
            memory = UserMemory(
                user_id=user_id,
                category=category,
                memory_key=memory_key,
                memory_value=memory_value,
                confidence=confidence,
                source=source,
                source_context=source_context,
            )
            self.db.add(memory)
            self.db.commit()
            self.db.refresh(memory)
            logger.info(f"Saved new memory: {category}/{memory_key} for user {user_id}")
            return memory

    def get_memories(self, user_id: str, category: Optional[str] = None) -> List[UserMemory]:
        """Get all memories for a user, optionally filtered by category"""
        query = self.db.query(UserMemory).filter(UserMemory.user_id == user_id)
        if category:
            query = query.filter(UserMemory.category == category)
        return query.order_by(UserMemory.category, UserMemory.memory_key).all()

    def delete_memory(self, user_id: str, memory_id: str) -> bool:
        """Delete a specific memory (user must own it)"""
        memory = self.db.query(UserMemory).filter(
            UserMemory.id == memory_id,
            UserMemory.user_id == user_id,
        ).first()
        if memory:
            self.db.delete(memory)
            self.db.commit()
            logger.info(f"Deleted memory {memory_id} for user {user_id}")
            return True
        return False

    def delete_all_memories(self, user_id: str) -> int:
        """Delete all memories for a user (privacy reset)"""
        count = self.db.query(UserMemory).filter(
            UserMemory.user_id == user_id
        ).delete()
        self.db.commit()
        logger.info(f"Deleted {count} memories for user {user_id}")
        return count

    def record_city_activity(
        self,
        user_id: str,
        city: str,
        state: str,
        region: Optional[str] = None,
    ) -> UserCityActivity:
        """
        Record city activity from an analysis.
        Increments count if city already tracked.
        """
        existing = self.db.query(UserCityActivity).filter(
            UserCityActivity.user_id == user_id,
            UserCityActivity.city == city,
            UserCityActivity.state == state,
        ).first()

        if existing:
            existing.activity_count += 1
            existing.last_activity = datetime.utcnow()
            if region and not existing.region:
                existing.region = region
            self.db.commit()
            logger.info(f"Updated city activity: {city}, {state} (count: {existing.activity_count})")
            return existing
        else:
            activity = UserCityActivity(
                user_id=user_id,
                city=city,
                state=state,
                region=region,
            )
            self.db.add(activity)
            self.db.commit()
            self.db.refresh(activity)
            logger.info(f"Recorded new city activity: {city}, {state}")
            return activity

    def get_city_activities(self, user_id: str, limit: int = 10) -> List[UserCityActivity]:
        """Get recent city activities for a user"""
        return self.db.query(UserCityActivity).filter(
            UserCityActivity.user_id == user_id
        ).order_by(UserCityActivity.last_activity.desc()).limit(limit).all()

    def delete_city_activity(self, user_id: str, activity_id: str) -> bool:
        """Delete a specific city activity"""
        activity = self.db.query(UserCityActivity).filter(
            UserCityActivity.id == activity_id,
            UserCityActivity.user_id == user_id,
        ).first()
        if activity:
            self.db.delete(activity)
            self.db.commit()
            return True
        return False

    def delete_all_city_activities(self, user_id: str) -> int:
        """Delete all city activities for a user"""
        count = self.db.query(UserCityActivity).filter(
            UserCityActivity.user_id == user_id
        ).delete()
        self.db.commit()
        return count

    def format_memories_for_prompt(self, user_id: str) -> str:
        """
        Format user memories and city activities for injection into system prompt.
        Returns empty string if no memories exist.
        """
        memories = self.get_memories(user_id)
        cities = self.get_city_activities(user_id, limit=5)

        if not memories and not cities:
            return ""

        lines = ["USER PREFERENCES (from previous conversations):"]

        # Group memories by category
        by_category: Dict[str, List[UserMemory]] = {}
        for mem in memories:
            if mem.category not in by_category:
                by_category[mem.category] = []
            by_category[mem.category].append(mem)

        # Output in preferred order
        for category in CATEGORY_ORDER:
            if category in by_category:
                label = CATEGORY_LABELS.get(category, category.title())
                items = "; ".join(
                    f"{m.memory_key}: {m.memory_value}"
                    for m in by_category[category]
                )
                lines.append(f"- {label}: {items}")

        # Add city activities
        if cities:
            city_list = ", ".join(f"{c.city}, {c.state}" for c in cities)
            lines.append(f"- Active search areas: {city_list}")

        return "\n".join(lines)

    def get_all_user_data(self, user_id: str) -> Dict[str, Any]:
        """Get all memories and city activities for API response"""
        memories = self.get_memories(user_id)
        cities = self.get_city_activities(user_id)

        return {
            "memories": [
                {
                    "id": m.id,
                    "category": m.category,
                    "key": m.memory_key,
                    "value": m.memory_value,
                    "confidence": m.confidence,
                    "source": m.source,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                    "updated_at": m.updated_at.isoformat() if m.updated_at else None,
                }
                for m in memories
            ],
            "city_activities": [
                {
                    "id": c.id,
                    "city": c.city,
                    "state": c.state,
                    "region": c.region,
                    "activity_count": c.activity_count,
                    "last_activity": c.last_activity.isoformat() if c.last_activity else None,
                }
                for c in cities
            ],
        }
