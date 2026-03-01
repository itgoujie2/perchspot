"""
Alert service with Redis-based deduplication.

Sends operational alerts via AWS SES, with a configurable cooldown
per alert_type to prevent alert storms.
"""
import logging
from typing import Optional

import redis

from app.config import settings
from app.services.email.ses_client import SESClient

logger = logging.getLogger(__name__)

DEFAULT_COOLDOWN_SECONDS = 15 * 60  # 15 minutes


class AlertService:
    """Send operational alerts with Redis cooldown dedup."""

    def __init__(self):
        self._ses: Optional[SESClient] = None
        self._redis: Optional[redis.Redis] = None

        try:
            self._redis = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
            self._redis.ping()
        except Exception as e:
            logger.warning(f"AlertService: Redis unavailable — cooldown disabled: {e}")
            self._redis = None

    @property
    def ses(self) -> SESClient:
        if self._ses is None:
            self._ses = SESClient()
        return self._ses

    @property
    def recipient(self) -> str:
        """Alert recipient — falls back to SES_FROM_EMAIL (admin inbox)."""
        return settings.ALERT_EMAIL or settings.SES_FROM_EMAIL

    def send_alert(
        self,
        alert_type: str,
        subject: str,
        body_text: str,
        cooldown: int = DEFAULT_COOLDOWN_SECONDS,
    ) -> bool:
        """
        Send an alert email if not in cooldown.

        Args:
            alert_type: Unique key for dedup (e.g. "qps_warning", "health_down")
            subject: Email subject
            body_text: Plain-text body
            cooldown: Seconds to suppress duplicate alerts (0 = always send)

        Returns:
            True if alert was sent, False if suppressed or failed.
        """
        cooldown_key = f"alert:cooldown:{alert_type}"

        # Check cooldown
        if self._redis and cooldown > 0:
            try:
                if self._redis.exists(cooldown_key):
                    logger.debug(f"Alert '{alert_type}' suppressed (cooldown active)")
                    return False
            except Exception:
                pass  # Redis down — send anyway

        to_email = self.recipient
        if not to_email:
            logger.warning(f"Alert '{alert_type}' skipped — no recipient configured")
            return False

        # Strip display name if present (e.g. "Perchspot <hello@perchspot.com>" -> "hello@perchspot.com")
        if "<" in to_email and ">" in to_email:
            to_email = to_email.split("<")[1].rstrip(">")

        html_body = f"<pre>{body_text}</pre>"

        try:
            result = self.ses.send_email(
                to_email=to_email,
                subject=f"[Perchspot Alert] {subject}",
                html_body=html_body,
                text_body=body_text,
            )

            if result.get("success"):
                logger.info(f"Alert '{alert_type}' sent to {to_email}")
                # Set cooldown
                if self._redis and cooldown > 0:
                    try:
                        self._redis.setex(cooldown_key, cooldown, "1")
                    except Exception:
                        pass
                return True
            else:
                logger.error(f"Alert '{alert_type}' failed: {result.get('error')}")
                return False

        except Exception as e:
            logger.exception(f"Alert '{alert_type}' exception: {e}")
            return False
