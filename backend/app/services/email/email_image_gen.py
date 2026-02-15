"""
Email image generation using Matplotlib/Pillow
Generates visual summary cards for email campaigns
"""
import io
import logging
from typing import Optional
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image

logger = logging.getLogger(__name__)

# Brand colors
BRAND_PRIMARY = '#2563EB'  # Blue
BRAND_SECONDARY = '#1E40AF'  # Darker blue
BRAND_SUCCESS = '#10B981'  # Green
BRAND_DANGER = '#EF4444'  # Red
BRAND_LIGHT = '#F8FAFC'  # Light background
BRAND_TEXT = '#1E293B'  # Dark text
BRAND_MUTED = '#64748B'  # Muted text


class EmailImageGenerator:
    """Generate images for email campaigns"""

    def __init__(self):
        # Set matplotlib to use non-interactive backend
        plt.switch_backend('Agg')

    def generate_city_summary_card(
        self,
        city: str,
        state: str,
        property_count: int,
        avg_price: float,
        price_change_pct: Optional[float] = None,
        width: int = 600,
        height: int = 200,
    ) -> bytes:
        """
        Generate a city summary card image.

        ┌─────────────────────────────────────────────────┐
        │  Austin, TX                          ▲ 2.3%    │
        │  23 new listings                   vs last week │
        │  Avg: $575,000                                  │
        └─────────────────────────────────────────────────┘

        Args:
            city: City name
            state: State abbreviation
            property_count: Number of new listings
            avg_price: Average listing price
            price_change_pct: Week-over-week price change (can be negative)
            width: Image width in pixels
            height: Image height in pixels

        Returns:
            PNG image as bytes
        """
        # Create figure with correct DPI for pixel dimensions
        dpi = 100
        fig_width = width / dpi
        fig_height = height / dpi

        fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=dpi)

        # Background
        ax.set_facecolor(BRAND_LIGHT)
        fig.patch.set_facecolor(BRAND_LIGHT)

        # Remove axes
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')

        # Add rounded rectangle border
        rect = patches.FancyBboxPatch(
            (0.02, 0.05), 0.96, 0.90,
            boxstyle="round,pad=0.02,rounding_size=0.03",
            facecolor='white',
            edgecolor=BRAND_PRIMARY,
            linewidth=2,
        )
        ax.add_patch(rect)

        # City name (large, bold)
        ax.text(
            0.06, 0.75,
            f"{city}, {state}",
            fontsize=24,
            fontweight='bold',
            color=BRAND_TEXT,
            verticalalignment='center',
        )

        # Property count
        ax.text(
            0.06, 0.45,
            f"{property_count} new listing{'s' if property_count != 1 else ''}",
            fontsize=16,
            color=BRAND_MUTED,
            verticalalignment='center',
        )

        # Average price
        price_formatted = self._format_price(avg_price)
        ax.text(
            0.06, 0.20,
            f"Avg: {price_formatted}",
            fontsize=18,
            fontweight='semibold',
            color=BRAND_TEXT,
            verticalalignment='center',
        )

        # Price change indicator (right side)
        if price_change_pct is not None:
            if price_change_pct >= 0:
                arrow = '▲'
                color = BRAND_SUCCESS
            else:
                arrow = '▼'
                color = BRAND_DANGER

            ax.text(
                0.92, 0.70,
                f"{arrow} {abs(price_change_pct):.1f}%",
                fontsize=18,
                fontweight='bold',
                color=color,
                verticalalignment='center',
                horizontalalignment='right',
            )

            ax.text(
                0.92, 0.45,
                "vs last week",
                fontsize=12,
                color=BRAND_MUTED,
                verticalalignment='center',
                horizontalalignment='right',
            )

        # Convert to PNG bytes
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.1)
        plt.close(fig)
        buf.seek(0)

        return buf.read()

    def generate_property_card(
        self,
        address: str,
        price: float,
        beds: int,
        baths: float,
        sqft: int,
        score: Optional[int] = None,
        width: int = 600,
        height: int = 150,
    ) -> bytes:
        """
        Generate a property card image.

        ┌─────────────────────────────────────────────────┐
        │  $575,000                             Score: 85 │
        │  123 Main St, Austin, TX                        │
        │  3 bd • 2 ba • 1,850 sqft                       │
        └─────────────────────────────────────────────────┘

        Args:
            address: Property address
            price: Listing price
            beds: Number of bedrooms
            baths: Number of bathrooms
            sqft: Square footage
            score: Optional Perchspot score (0-100)
            width: Image width in pixels
            height: Image height in pixels

        Returns:
            PNG image as bytes
        """
        dpi = 100
        fig_width = width / dpi
        fig_height = height / dpi

        fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=dpi)

        ax.set_facecolor('white')
        fig.patch.set_facecolor('white')

        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')

        # Border
        rect = patches.FancyBboxPatch(
            (0.01, 0.05), 0.98, 0.90,
            boxstyle="round,pad=0.01,rounding_size=0.02",
            facecolor='white',
            edgecolor='#E2E8F0',
            linewidth=1.5,
        )
        ax.add_patch(rect)

        # Price (large, bold)
        price_formatted = self._format_price(price)
        ax.text(
            0.04, 0.75,
            price_formatted,
            fontsize=22,
            fontweight='bold',
            color=BRAND_PRIMARY,
            verticalalignment='center',
        )

        # Score badge (right side)
        if score is not None:
            # Score circle background
            circle = patches.Circle(
                (0.92, 0.70), 0.08,
                facecolor=self._get_score_color(score),
                edgecolor='white',
                linewidth=2,
            )
            ax.add_patch(circle)

            ax.text(
                0.92, 0.70,
                str(score),
                fontsize=16,
                fontweight='bold',
                color='white',
                verticalalignment='center',
                horizontalalignment='center',
            )

        # Address (truncate if too long)
        display_address = address if len(address) <= 45 else address[:42] + '...'
        ax.text(
            0.04, 0.45,
            display_address,
            fontsize=14,
            color=BRAND_TEXT,
            verticalalignment='center',
        )

        # Property details
        baths_str = f"{int(baths)}" if baths == int(baths) else f"{baths:.1f}"
        details = f"{beds} bd  •  {baths_str} ba  •  {sqft:,} sqft"
        ax.text(
            0.04, 0.18,
            details,
            fontsize=13,
            color=BRAND_MUTED,
            verticalalignment='center',
        )

        # Convert to PNG bytes
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.05)
        plt.close(fig)
        buf.seek(0)

        return buf.read()

    def generate_header_image(
        self,
        date_range: str,
        width: int = 600,
        height: int = 120,
    ) -> bytes:
        """
        Generate email header image with Perchspot branding.

        Args:
            date_range: Date range string (e.g., "Feb 9-15, 2026")
            width: Image width
            height: Image height

        Returns:
            PNG image as bytes
        """
        dpi = 100
        fig_width = width / dpi
        fig_height = height / dpi

        fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=dpi)

        # Gradient-like background
        ax.set_facecolor(BRAND_PRIMARY)
        fig.patch.set_facecolor(BRAND_PRIMARY)

        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')

        # Title
        ax.text(
            0.5, 0.65,
            "Your Weekly Property Update",
            fontsize=22,
            fontweight='bold',
            color='white',
            verticalalignment='center',
            horizontalalignment='center',
        )

        # Date range
        ax.text(
            0.5, 0.30,
            date_range,
            fontsize=14,
            color='#BFDBFE',  # Light blue
            verticalalignment='center',
            horizontalalignment='center',
        )

        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0)
        plt.close(fig)
        buf.seek(0)

        return buf.read()

    def _format_price(self, price: float) -> str:
        """Format price as currency string"""
        if price >= 1_000_000:
            return f"${price / 1_000_000:.2f}M"
        elif price >= 1_000:
            return f"${price / 1_000:.0f}K"
        else:
            return f"${price:,.0f}"

    def _get_score_color(self, score: int) -> str:
        """Get color for score badge based on value"""
        if score >= 80:
            return BRAND_SUCCESS  # Green
        elif score >= 60:
            return '#F59E0B'  # Amber
        else:
            return BRAND_DANGER  # Red
