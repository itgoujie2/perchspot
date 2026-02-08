"""
IP-based usage tracking for free tier analyses.
"""
from sqlalchemy.orm import Session
from app.models.user import IpUsage
from app.config import settings

FREE_ANALYSIS_LIMIT = settings.FREE_ANALYSES_PER_IP


def get_ip_analysis_count(db: Session, ip: str) -> int:
    """Return the number of analyses recorded for this IP."""
    return db.query(IpUsage).filter(IpUsage.ip_address == ip).count()


def record_ip_analysis(db: Session, ip: str, address: str) -> None:
    """Record that this IP used a free analysis for the given address."""
    entry = IpUsage(ip_address=ip, address=address)
    db.add(entry)
    db.commit()
