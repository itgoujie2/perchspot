"""
SharedReport SQLAlchemy model for public shareable property reports
"""
from sqlalchemy import Column, String, CHAR, Text, DateTime, ForeignKey, Index, Integer, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import secrets
import string

from app.database.connection import Base


def generate_share_code(length: int = 8) -> str:
    """Generate a short, URL-safe share code"""
    alphabet = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


class SharedReport(Base):
    """
    Stores publicly shareable property analysis reports.

    When a user shares a report, we create a cached copy that anyone
    can view without logging in or having credits.
    """
    __tablename__ = "shared_reports"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    share_code = Column(String(16), unique=True, nullable=False, default=generate_share_code)

    # Property info
    address = Column(String(500), nullable=False)

    # Who shared it (optional - could be anonymous/guest)
    user_id = Column(CHAR(36), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    # Cached analysis data (JSON blob with everything)
    report_data = Column(JSON, nullable=False)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Optional expiration
    view_count = Column(Integer, default=0)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index('idx_shared_reports_code', 'share_code'),
        Index('idx_shared_reports_address', 'address'),
        Index('idx_shared_reports_user', 'user_id'),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    )

    def get_share_url(self, base_url: str) -> str:
        """Generate the full share URL"""
        return f"{base_url}/share/{self.share_code}"
