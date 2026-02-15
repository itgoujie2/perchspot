"""
AWS SES Email Client for sending emails
"""
import logging
from typing import Optional, Dict, Any
import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)


class SESClient:
    """AWS Simple Email Service client for sending emails"""

    def __init__(self):
        self.client = boto3.client(
            'ses',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        self.from_email = settings.SES_FROM_EMAIL

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send an email via AWS SES.

        Args:
            to_email: Recipient email address
            subject: Email subject line
            html_body: HTML content of the email
            text_body: Plain text content (fallback)

        Returns:
            dict with 'success', 'message_id', and optionally 'error'
        """
        if not text_body:
            # Create basic text version by stripping HTML
            text_body = self._html_to_text(html_body)

        try:
            response = self.client.send_email(
                Source=self.from_email,
                Destination={
                    'ToAddresses': [to_email],
                },
                Message={
                    'Subject': {
                        'Data': subject,
                        'Charset': 'UTF-8',
                    },
                    'Body': {
                        'Text': {
                            'Data': text_body,
                            'Charset': 'UTF-8',
                        },
                        'Html': {
                            'Data': html_body,
                            'Charset': 'UTF-8',
                        },
                    },
                },
            )

            message_id = response.get('MessageId')
            logger.info(f"Email sent to {to_email}, MessageId: {message_id}")

            return {
                'success': True,
                'message_id': message_id,
            }

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            logger.error(f"SES error sending to {to_email}: {error_code} - {error_message}")

            return {
                'success': False,
                'error': f"{error_code}: {error_message}",
            }

        except Exception as e:
            logger.exception(f"Unexpected error sending email to {to_email}")
            return {
                'success': False,
                'error': str(e),
            }

    def send_raw_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
        attachments: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Send a raw email with optional attachments via AWS SES.
        For emails with embedded images or attachments.

        Args:
            to_email: Recipient email address
            subject: Email subject line
            html_body: HTML content
            text_body: Plain text content
            attachments: List of dicts with 'filename', 'data', 'content_type'

        Returns:
            dict with 'success', 'message_id', and optionally 'error'
        """
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.base import MIMEBase
        from email import encoders

        if not text_body:
            text_body = self._html_to_text(html_body)

        # Create message container
        msg = MIMEMultipart('mixed')
        msg['Subject'] = subject
        msg['From'] = self.from_email
        msg['To'] = to_email

        # Create alternative part for text/html
        msg_body = MIMEMultipart('alternative')
        msg_body.attach(MIMEText(text_body, 'plain', 'utf-8'))
        msg_body.attach(MIMEText(html_body, 'html', 'utf-8'))
        msg.attach(msg_body)

        # Add attachments
        if attachments:
            for attachment in attachments:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment['data'])
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f"attachment; filename={attachment['filename']}",
                )
                if 'content_type' in attachment:
                    part.replace_header('Content-Type', attachment['content_type'])
                msg.attach(part)

        try:
            response = self.client.send_raw_email(
                Source=self.from_email,
                Destinations=[to_email],
                RawMessage={'Data': msg.as_string()},
            )

            message_id = response.get('MessageId')
            logger.info(f"Raw email sent to {to_email}, MessageId: {message_id}")

            return {
                'success': True,
                'message_id': message_id,
            }

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            logger.error(f"SES error sending raw email to {to_email}: {error_code} - {error_message}")

            return {
                'success': False,
                'error': f"{error_code}: {error_message}",
            }

        except Exception as e:
            logger.exception(f"Unexpected error sending raw email to {to_email}")
            return {
                'success': False,
                'error': str(e),
            }

    def verify_email_identity(self, email: str) -> bool:
        """
        Request verification for an email address.
        Used during development/testing with SES sandbox.
        """
        try:
            self.client.verify_email_identity(EmailAddress=email)
            logger.info(f"Verification email sent to {email}")
            return True
        except ClientError as e:
            logger.error(f"Error verifying email {email}: {e}")
            return False

    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text (basic conversion)"""
        import re
        # Remove HTML tags
        text = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
        text = re.sub(r'<p[^>]*>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        # Decode HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        # Clean up whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        return text.strip()
