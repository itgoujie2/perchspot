"""Models package"""
from app.models.database import (
    Property,
    PropertyDataSource,
    PropertyImage,
    School,
    PropertySchool,
    PropertyAnalysis,
    AnalysisReport,
    APIUsageLog,
    APICache,
    AnalysisJob,
    ComparableProperty,
)
from app.models.user import User, CreditTransaction, IpUsage, Purchase
from app.models.memory import UserMemory, UserCityActivity
from app.models.similar_homes import UserSimilarHome
from app.models.referral import Referral
from app.models.favorite import UserFavorite
from app.models.shared_report import SharedReport
from app.models.email_preference import EmailPreference
from app.models.email_campaign_log import EmailCampaignLog

__all__ = [
    "Property",
    "PropertyDataSource",
    "PropertyImage",
    "School",
    "PropertySchool",
    "PropertyAnalysis",
    "AnalysisReport",
    "APIUsageLog",
    "APICache",
    "AnalysisJob",
    "ComparableProperty",
    "User",
    "CreditTransaction",
    "IpUsage",
    "Purchase",
    "UserMemory",
    "UserCityActivity",
    "UserSimilarHome",
    "Referral",
    "UserFavorite",
    "SharedReport",
    "EmailPreference",
    "EmailCampaignLog",
]
