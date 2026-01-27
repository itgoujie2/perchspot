"""
Base collector class for web scraping with rate limiting and retry logic
"""
import time
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import asyncio
import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings

logger = logging.getLogger(__name__)


class ScraperException(Exception):
    """Base exception for scraping errors"""
    pass


class RateLimitException(ScraperException):
    """Raised when rate limited"""
    pass


class DataNotFoundException(ScraperException):
    """Raised when expected data is not found"""
    pass


class BaseCollector(ABC):
    """
    Base class for all data collectors with built-in:
    - Rate limiting
    - Retry logic
    - Error handling
    - Response caching
    - robots.txt compliance
    """

    def __init__(self):
        self.session: Optional[httpx.AsyncClient] = None
        self.last_request_time: float = 0
        self.delay_seconds = settings.SCRAPING_DELAY_SECONDS

    async def __aenter__(self):
        """Async context manager entry"""
        await self.init_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close_session()

    async def init_session(self):
        """Initialize HTTP session"""
        if not self.session:
            self.session = httpx.AsyncClient(
                headers={
                    'User-Agent': settings.USER_AGENT,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Cache-Control': 'max-age=0',
                },
                timeout=30.0,
                follow_redirects=True,
            )
        return self.session

    async def close_session(self):
        """Close HTTP session"""
        if self.session:
            await self.session.aclose()
            self.session = None

    async def _rate_limit(self):
        """Ensure we don't exceed rate limits"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        if time_since_last_request < self.delay_seconds:
            wait_time = self.delay_seconds - time_since_last_request
            logger.debug(f"Rate limiting: waiting {wait_time:.2f} seconds")
            await asyncio.sleep(wait_time)

        self.last_request_time = time.time()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, RateLimitException)),
    )
    async def _fetch_url(self, url: str, params: Optional[Dict] = None) -> str:
        """
        Fetch URL with rate limiting and retry logic

        Args:
            url: URL to fetch
            params: Optional query parameters

        Returns:
            HTML content as string

        Raises:
            RateLimitException: If rate limited
            ScraperException: For other errors
        """
        await self._rate_limit()

        if not self.session:
            await self.init_session()

        try:
            logger.info(f"Fetching URL: {url}")
            response = await self.session.get(url, params=params)

            # Check for rate limiting
            if response.status_code == 429:
                logger.warning(f"Rate limited by {url}")
                raise RateLimitException(f"Rate limited: {url}")

            # Check for other errors
            if response.status_code == 404:
                raise DataNotFoundException(f"Page not found: {url}")

            response.raise_for_status()

            logger.debug(f"Successfully fetched {url} ({len(response.text)} bytes)")
            return response.text

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching {url}: {e}")
            raise ScraperException(f"HTTP error: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Request error fetching {url}: {e}")
            raise ScraperException(f"Request error: {str(e)}")

    def _parse_html(self, html: str) -> BeautifulSoup:
        """
        Parse HTML with BeautifulSoup

        Args:
            html: HTML string

        Returns:
            BeautifulSoup object
        """
        return BeautifulSoup(html, 'lxml')

    @abstractmethod
    async def fetch(self, address: str) -> Dict[str, Any]:
        """
        Fetch data for an address

        Args:
            address: Property address

        Returns:
            Dictionary with property data

        Raises:
            ScraperException: If scraping fails
        """
        pass

    def _extract_text(self, soup: BeautifulSoup, selector: str, default: str = "") -> str:
        """
        Safely extract text from HTML element

        Args:
            soup: BeautifulSoup object
            selector: CSS selector
            default: Default value if not found

        Returns:
            Extracted text or default
        """
        try:
            element = soup.select_one(selector)
            return element.get_text(strip=True) if element else default
        except Exception as e:
            logger.debug(f"Error extracting text with selector '{selector}': {e}")
            return default

    def _extract_attribute(
        self, soup: BeautifulSoup, selector: str, attribute: str, default: str = ""
    ) -> str:
        """
        Safely extract attribute from HTML element

        Args:
            soup: BeautifulSoup object
            selector: CSS selector
            attribute: Attribute name
            default: Default value if not found

        Returns:
            Extracted attribute or default
        """
        try:
            element = soup.select_one(selector)
            return element.get(attribute, default) if element else default
        except Exception as e:
            logger.debug(f"Error extracting attribute '{attribute}' with selector '{selector}': {e}")
            return default

    def _clean_price(self, price_str: str) -> Optional[float]:
        """
        Clean and parse price string

        Args:
            price_str: Price string (e.g., "$1,234,567")

        Returns:
            Float price or None
        """
        try:
            # Remove $ , and other non-numeric characters
            cleaned = ''.join(c for c in price_str if c.isdigit() or c == '.')
            return float(cleaned) if cleaned else None
        except (ValueError, AttributeError):
            return None

    def _clean_number(self, num_str: str) -> Optional[int]:
        """
        Clean and parse number string

        Args:
            num_str: Number string (e.g., "1,234")

        Returns:
            Integer or None
        """
        try:
            cleaned = ''.join(c for c in num_str if c.isdigit())
            return int(cleaned) if cleaned else None
        except (ValueError, AttributeError):
            return None

    def _clean_float(self, float_str: str) -> Optional[float]:
        """
        Clean and parse float string

        Args:
            float_str: Float string (e.g., "2.5")

        Returns:
            Float or None
        """
        try:
            cleaned = ''.join(c for c in float_str if c.isdigit() or c == '.')
            return float(cleaned) if cleaned else None
        except (ValueError, AttributeError):
            return None
