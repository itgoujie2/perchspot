"""
Email campaign Celery tasks
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from app.tasks.celery_app import celery_app
from app.database.connection import SessionLocal
from app.models.user import User
from app.models.email_preference import EmailPreference
from app.models.email_campaign_log import EmailCampaignLog
from app.models.memory import UserCityActivity
from app.models.similar_homes import UserSimilarHome
from app.services.email.ses_client import SESClient
from app.services.email.email_renderer import EmailRenderer

logger = logging.getLogger(__name__)


def get_user_cities(db: Session, user_id: str, days: int = 30) -> List[Dict[str, Any]]:
    """
    Get cities the user has searched in the last N days.

    Returns list of dicts with city data and statistics.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    activities = (
        db.query(UserCityActivity)
        .filter(
            UserCityActivity.user_id == user_id,
            UserCityActivity.last_activity >= cutoff,
        )
        .order_by(UserCityActivity.activity_count.desc())
        .limit(5)
        .all()
    )

    cities = []
    for activity in activities:
        cities.append({
            'city': activity.city,
            'state': activity.state,
            'region': activity.region,
            'property_count': activity.activity_count,
            'avg_price': None,  # Could be enhanced with actual price data
            'price_change_pct': None,  # Could be enhanced with market data
        })

    return cities


def get_user_recommendations(db: Session, user_id: str, limit: int = 6) -> List[Dict[str, Any]]:
    """
    Get unshown property recommendations for a user.

    Returns list of property dicts.
    """
    properties = (
        db.query(UserSimilarHome)
        .filter(
            UserSimilarHome.user_id == user_id,
            UserSimilarHome.shown_to_user == False,
        )
        .order_by(UserSimilarHome.created_at.desc())
        .limit(limit)
        .all()
    )

    results = []
    for prop in properties:
        results.append({
            'id': prop.id,
            'address': prop.similar_address,
            'price': float(prop.price) if prop.price else 0,
            'beds': prop.bedrooms or 0,
            'baths': float(prop.bathrooms) if prop.bathrooms else 0,
            'sqft': prop.sqft or 0,
            'url': prop.redfin_url,
            'score': None,  # Could be enhanced with pre-computed scores
        })

    return results


def mark_properties_as_shown(db: Session, property_ids: List[str]):
    """Mark similar homes as shown to user"""
    if property_ids:
        db.query(UserSimilarHome).filter(
            UserSimilarHome.id.in_(property_ids)
        ).update({'shown_to_user': True}, synchronize_session=False)
        db.commit()


@celery_app.task(name="send_weekly_digest_emails", bind=True, max_retries=3)
def send_weekly_digest_emails(self):
    """
    Send weekly digest emails to all eligible users.

    Runs every Sunday at 9 AM UTC.
    """
    logger.info("Starting weekly digest email campaign")

    db = SessionLocal()
    ses_client = SESClient()
    renderer = EmailRenderer()

    sent_count = 0
    error_count = 0

    try:
        # Get users who should receive weekly digest
        # Either they have explicit preference enabled, or no preference (default opt-in)
        users_with_prefs = (
            db.query(User, EmailPreference)
            .outerjoin(EmailPreference, User.id == EmailPreference.user_id)
            .filter(
                or_(
                    EmailPreference.weekly_digest == True,
                    EmailPreference.id == None,  # No preference = default enabled
                )
            )
            .all()
        )

        logger.info(f"Found {len(users_with_prefs)} users eligible for weekly digest")

        for user, prefs in users_with_prefs:
            try:
                # Get user's searched cities
                cities = get_user_cities(db, user.id)

                if not cities:
                    # Skip users with no city activity
                    logger.debug(f"Skipping user {user.email} - no city activity")
                    continue

                # Get property recommendations
                properties = get_user_recommendations(db, user.id)

                # Get or create unsubscribe token
                if not prefs:
                    prefs = EmailPreference(user_id=user.id)
                    db.add(prefs)
                    db.commit()
                    db.refresh(prefs)

                # Render email
                html_content = renderer.render_weekly_digest(
                    user_email=user.email,
                    unsubscribe_token=prefs.unsubscribe_token,
                    cities=cities,
                    properties=properties,
                )

                # Generate subject line
                subject = renderer.get_weekly_digest_subject(
                    cities=cities,
                    property_count=len(properties),
                )

                # Send email
                result = ses_client.send_email(
                    to_email=user.email,
                    subject=subject,
                    html_body=html_content,
                )

                # Log the campaign
                log_entry = EmailCampaignLog(
                    user_id=user.id,
                    email_type='weekly_digest',
                    recipient_email=user.email,
                    subject=subject,
                    cities_included=[c['city'] for c in cities],
                    properties_count=len(properties),
                    status='sent' if result['success'] else 'failed',
                    ses_message_id=result.get('message_id'),
                    error_message=result.get('error'),
                    sent_at=datetime.utcnow() if result['success'] else None,
                )
                db.add(log_entry)

                if result['success']:
                    sent_count += 1
                    # Mark properties as shown
                    property_ids = [p['id'] for p in properties if 'id' in p]
                    mark_properties_as_shown(db, property_ids)
                    logger.info(f"Sent weekly digest to {user.email}")
                else:
                    error_count += 1
                    logger.error(f"Failed to send to {user.email}: {result.get('error')}")

                db.commit()

            except Exception as e:
                error_count += 1
                logger.exception(f"Error processing user {user.email}: {e}")

                # Log the failure
                log_entry = EmailCampaignLog(
                    user_id=user.id,
                    email_type='weekly_digest',
                    recipient_email=user.email,
                    subject='Weekly Digest',
                    status='failed',
                    error_message=str(e),
                )
                db.add(log_entry)
                db.commit()

        logger.info(f"Weekly digest campaign complete: {sent_count} sent, {error_count} errors")

        return {
            'sent': sent_count,
            'errors': error_count,
            'total': len(users_with_prefs),
        }

    except Exception as e:
        logger.exception(f"Fatal error in weekly digest campaign: {e}")
        raise self.retry(exc=e, countdown=300)  # Retry in 5 minutes

    finally:
        db.close()


@celery_app.task(name="send_test_digest_email")
def send_test_digest_email(user_email: str):
    """
    Send a test digest email to a specific user.
    Used for testing/debugging.
    """
    logger.info(f"Sending test digest email to {user_email}")

    db = SessionLocal()
    ses_client = SESClient()
    renderer = EmailRenderer()

    try:
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            return {'success': False, 'error': 'User not found'}

        # Get or create preferences
        prefs = db.query(EmailPreference).filter(EmailPreference.user_id == user.id).first()
        if not prefs:
            prefs = EmailPreference(user_id=user.id)
            db.add(prefs)
            db.commit()
            db.refresh(prefs)

        # Get user's data
        cities = get_user_cities(db, user.id)
        properties = get_user_recommendations(db, user.id)

        # Use sample data if user has no activity
        if not cities:
            cities = [
                {'city': 'Austin', 'state': 'TX', 'property_count': 15, 'avg_price': 575000, 'price_change_pct': 2.3},
                {'city': 'Denver', 'state': 'CO', 'property_count': 8, 'avg_price': 625000, 'price_change_pct': -1.2},
            ]

        if not properties:
            properties = [
                {'address': '123 Main St, Austin, TX 78701', 'price': 575000, 'beds': 3, 'baths': 2, 'sqft': 1850, 'score': 85},
                {'address': '456 Oak Ave, Austin, TX 78702', 'price': 495000, 'beds': 2, 'baths': 2, 'sqft': 1400, 'score': 78},
                {'address': '789 Pine Blvd, Denver, CO 80202', 'price': 650000, 'beds': 4, 'baths': 3, 'sqft': 2200, 'score': 82},
            ]

        # Render and send
        html_content = renderer.render_weekly_digest(
            user_email=user.email,
            unsubscribe_token=prefs.unsubscribe_token,
            cities=cities,
            properties=properties,
        )

        subject = "[TEST] " + renderer.get_weekly_digest_subject(cities, len(properties))

        result = ses_client.send_email(
            to_email=user.email,
            subject=subject,
            html_body=html_content,
        )

        return result

    except Exception as e:
        logger.exception(f"Error sending test email: {e}")
        return {'success': False, 'error': str(e)}

    finally:
        db.close()
