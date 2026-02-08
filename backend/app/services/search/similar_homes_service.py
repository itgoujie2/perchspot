"""
Similar Homes Service - CRUD operations for user similar homes
"""
import logging
from typing import Dict, List, Any
from sqlalchemy.orm import Session

from app.models.similar_homes import UserSimilarHome

logger = logging.getLogger(__name__)


class SimilarHomesService:
    """Service for managing similar homes extracted during property analysis"""

    def __init__(self, db: Session):
        self.db = db

    def save_similar_homes(
        self,
        user_id: str,
        source_address: str,
        similar_homes: List[Dict[str, Any]]
    ) -> int:
        """
        Save extracted similar homes for a user.

        Args:
            user_id: The user's ID
            source_address: The property address they analyzed
            similar_homes: List of similar home dictionaries

        Returns:
            Number of homes saved (excludes duplicates)
        """
        saved = 0
        for home in similar_homes:
            address = home.get("address")
            if not address:
                continue

            # Skip if already exists for this user
            existing = self.db.query(UserSimilarHome).filter(
                UserSimilarHome.user_id == user_id,
                UserSimilarHome.similar_address == address
            ).first()

            if not existing:
                record = UserSimilarHome(
                    user_id=user_id,
                    source_address=source_address,
                    similar_address=address,
                    price=home.get("price"),
                    bedrooms=home.get("bedrooms"),
                    bathrooms=home.get("bathrooms"),
                    sqft=home.get("sqft"),
                    property_type=home.get("property_type"),
                    redfin_url=home.get("redfin_url"),
                )
                self.db.add(record)
                saved += 1

        if saved > 0:
            self.db.commit()
            logger.info(f"Saved {saved} similar homes for user {user_id}")

        return saved

    def get_recommendations(
        self,
        user_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get unshown similar homes for recommendations.

        Args:
            user_id: The user's ID
            limit: Maximum number of recommendations to return

        Returns:
            List of similar home dictionaries
        """
        homes = self.db.query(UserSimilarHome).filter(
            UserSimilarHome.user_id == user_id,
            UserSimilarHome.shown_to_user == False
        ).order_by(
            UserSimilarHome.created_at.desc()
        ).limit(limit).all()

        return [
            {
                "address": h.similar_address,
                "price": float(h.price) if h.price else None,
                "bedrooms": h.bedrooms,
                "bathrooms": float(h.bathrooms) if h.bathrooms else None,
                "sqft": h.sqft,
                "property_type": h.property_type,
                "redfin_url": h.redfin_url,
                "source": h.source_address,
            }
            for h in homes
        ]

    def mark_as_shown(self, user_id: str, addresses: List[str]) -> int:
        """
        Mark homes as shown to avoid re-recommending.

        Args:
            user_id: The user's ID
            addresses: List of similar_address values to mark

        Returns:
            Number of records updated
        """
        if not addresses:
            return 0

        updated = self.db.query(UserSimilarHome).filter(
            UserSimilarHome.user_id == user_id,
            UserSimilarHome.similar_address.in_(addresses)
        ).update(
            {"shown_to_user": True},
            synchronize_session=False
        )
        self.db.commit()
        return updated

    def get_all_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all similar homes for a user (shown and unshown).

        Args:
            user_id: The user's ID

        Returns:
            List of all similar home dictionaries
        """
        homes = self.db.query(UserSimilarHome).filter(
            UserSimilarHome.user_id == user_id
        ).order_by(
            UserSimilarHome.created_at.desc()
        ).all()

        return [
            {
                "address": h.similar_address,
                "price": float(h.price) if h.price else None,
                "bedrooms": h.bedrooms,
                "bathrooms": float(h.bathrooms) if h.bathrooms else None,
                "sqft": h.sqft,
                "property_type": h.property_type,
                "redfin_url": h.redfin_url,
                "source": h.source_address,
                "shown": h.shown_to_user,
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
            for h in homes
        ]

    def get_count_for_user(self, user_id: str) -> Dict[str, int]:
        """
        Get counts of similar homes for a user.

        Args:
            user_id: The user's ID

        Returns:
            Dict with total, shown, and unshown counts
        """
        total = self.db.query(UserSimilarHome).filter(
            UserSimilarHome.user_id == user_id
        ).count()

        shown = self.db.query(UserSimilarHome).filter(
            UserSimilarHome.user_id == user_id,
            UserSimilarHome.shown_to_user == True
        ).count()

        return {
            "total": total,
            "shown": shown,
            "unshown": total - shown,
        }
