"""
Email template renderer using Jinja2
"""
import logging
import os
import base64
from typing import List, Dict, Any, Optional
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings
from app.services.email.email_image_gen import EmailImageGenerator

logger = logging.getLogger(__name__)

# Get templates directory
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'templates', 'email')


class EmailRenderer:
    """Renders email templates with Jinja2"""

    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader(TEMPLATES_DIR),
            autoescape=select_autoescape(['html', 'xml']),
        )
        self.image_gen = EmailImageGenerator()

    def render_weekly_digest(
        self,
        user_email: str,
        unsubscribe_token: str,
        cities: List[Dict[str, Any]],
        properties: List[Dict[str, Any]],
        date_range: Optional[str] = None,
    ) -> str:
        """
        Render the weekly digest email template.

        Args:
            user_email: User's email address
            unsubscribe_token: Token for unsubscribe link
            cities: List of city data dicts with keys:
                - city: str
                - state: str
                - property_count: int
                - avg_price: float
                - price_change_pct: float (optional)
            properties: List of property dicts with keys:
                - address: str
                - price: float
                - beds: int
                - baths: float
                - sqft: int
                - score: int (optional)
                - url: str (optional)
            date_range: Optional date range string

        Returns:
            Rendered HTML string
        """
        if not date_range:
            # Generate date range for past week
            now = datetime.now()
            start = now.replace(day=now.day - 7)
            date_range = f"{start.strftime('%b %d')} - {now.strftime('%b %d, %Y')}"

        # Generate city summary images as base64
        city_images = []
        for city_data in cities[:5]:  # Limit to 5 cities
            try:
                img_bytes = self.image_gen.generate_city_summary_card(
                    city=city_data['city'],
                    state=city_data['state'],
                    property_count=city_data.get('property_count', 0),
                    avg_price=city_data.get('avg_price', 0),
                    price_change_pct=city_data.get('price_change_pct'),
                )
                img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                city_images.append({
                    **city_data,
                    'image_base64': img_base64,
                })
            except Exception as e:
                logger.error(f"Error generating city image for {city_data.get('city')}: {e}")
                city_images.append(city_data)

        # Build URLs
        base_url = self._get_base_url()
        unsubscribe_url = f"{base_url}/api/v1/email/unsubscribe/{unsubscribe_token}"
        preferences_url = f"{base_url}/settings/email-preferences"
        analyze_url = f"{base_url}/analyze"

        # Format properties for template
        formatted_properties = []
        for prop in properties[:6]:  # Limit to 6 properties
            formatted_properties.append({
                'address': prop.get('address', ''),
                'price_formatted': self._format_price(prop.get('price', 0)),
                'beds': prop.get('beds', 0),
                'baths': prop.get('baths', 0),
                'sqft': prop.get('sqft', 0),
                'sqft_formatted': f"{prop.get('sqft', 0):,}",
                'score': prop.get('score'),
                'url': prop.get('url', f"{base_url}/analyze?address={prop.get('address', '')}"),
            })

        # Render template
        template = self.env.get_template('weekly_digest.html')
        return template.render(
            user_email=user_email,
            date_range=date_range,
            cities=city_images,
            properties=formatted_properties,
            unsubscribe_url=unsubscribe_url,
            preferences_url=preferences_url,
            analyze_url=analyze_url,
            base_url=base_url,
            current_year=datetime.now().year,
        )

    def get_weekly_digest_subject(self, cities: List[Dict[str, Any]], property_count: int) -> str:
        """
        Generate a subject line for the weekly digest.

        Args:
            cities: List of city data
            property_count: Total number of properties

        Returns:
            Email subject line
        """
        if cities:
            primary_city = cities[0]['city']
            if len(cities) > 1:
                return f"Your Weekly Property Update - {primary_city} & more"
            else:
                return f"Your Weekly Property Update - {primary_city}"
        elif property_count > 0:
            return f"{property_count} New Listings in Your Areas This Week"
        else:
            return "Your Weekly Property Update"

    def _format_price(self, price: float) -> str:
        """Format price as currency string"""
        if not price:
            return "$0"
        if price >= 1_000_000:
            return f"${price / 1_000_000:.2f}M"
        elif price >= 1_000:
            return f"${price:,.0f}"
        else:
            return f"${price:.0f}"

    def _get_base_url(self) -> str:
        """Get the base URL for the frontend"""
        # Parse from CORS origins or use default
        origins = settings.CORS_ORIGINS.split(',')
        for origin in origins:
            origin = origin.strip()
            if 'perchspot' in origin or not origin.startswith('http://localhost'):
                return origin
        # Fallback to first origin or default
        return origins[0].strip() if origins else 'https://perchspot.com'
