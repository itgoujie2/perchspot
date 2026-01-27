"""
Chart and visualization generation using Matplotlib
"""
import io
import logging
from typing import Dict, Any, List
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server
import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger(__name__)


class ChartGenerator:
    """
    Generate charts and visualizations for reports
    """

    def __init__(self):
        # Set style
        plt.style.use('seaborn-v0_8-darkgrid')
        self.colors = {
            'primary': '#1976d2',
            'success': '#4caf50',
            'warning': '#ff9800',
            'danger': '#f44336',
            'info': '#2196f3'
        }

    def generate_score_bar_chart(
        self,
        category_scores: Dict[str, float],
        overall_score: float
    ) -> bytes:
        """
        Generate horizontal bar chart of category scores

        Args:
            category_scores: Dictionary of category names to scores
            overall_score: Overall property score

        Returns:
            PNG image as bytes
        """
        try:
            fig, ax = plt.subplots(figsize=(10, 6))

            # Prepare data
            categories = {
                'property_condition': 'Property Condition',
                'location_quality': 'Location Quality',
                'schools': 'Schools',
                'investment_value': 'Investment Value'
            }

            labels = [categories[k] for k in category_scores.keys()]
            scores = [float(category_scores[k]) for k in category_scores.keys()]

            # Create horizontal bar chart
            y_pos = np.arange(len(labels))
            bars = ax.barh(y_pos, scores, color=self.colors['primary'], alpha=0.8)

            # Customize
            ax.set_yticks(y_pos)
            ax.set_yticklabels(labels)
            ax.set_xlabel('Score (0-100)', fontsize=12, fontweight='bold')
            ax.set_title('Property Analysis Scores', fontsize=14, fontweight='bold', pad=20)
            ax.set_xlim(0, 100)

            # Add score labels on bars
            for i, (bar, score) in enumerate(zip(bars, scores)):
                width = bar.get_width()
                ax.text(width + 2, bar.get_y() + bar.get_height()/2,
                       f'{score:.0f}',
                       ha='left', va='center', fontsize=11, fontweight='bold')

            # Add vertical line for overall score
            ax.axvline(x=overall_score, color=self.colors['success'],
                      linestyle='--', linewidth=2, alpha=0.7,
                      label=f'Overall: {overall_score:.0f}')

            ax.legend(loc='lower right', fontsize=10)
            ax.grid(axis='x', alpha=0.3)

            plt.tight_layout()

            # Save to bytes
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            buf.seek(0)
            plt.close(fig)

            return buf.read()

        except Exception as e:
            logger.error(f"Error generating score bar chart: {e}", exc_info=True)
            raise

    def generate_score_gauge(self, score: float, grade: str) -> bytes:
        """
        Generate gauge/speedometer chart for overall score

        Args:
            score: Overall score (0-100)
            grade: Letter grade (A-F)

        Returns:
            PNG image as bytes
        """
        try:
            fig, ax = plt.subplots(figsize=(8, 5), subplot_kw={'projection': 'polar'})

            # Create gauge
            theta = np.linspace(0, np.pi, 100)

            # Background segments (F to A)
            segments = [
                (0, 60, self.colors['danger']),      # F (0-60)
                (60, 70, self.colors['warning']),    # D (60-70)
                (70, 80, '#fdd835'),                 # C (70-80)
                (80, 90, self.colors['info']),       # B (80-90)
                (90, 100, self.colors['success'])    # A (90-100)
            ]

            for start, end, color in segments:
                theta_seg = np.linspace(start/100 * np.pi, end/100 * np.pi, 20)
                r = np.ones_like(theta_seg)
                ax.fill_between(theta_seg, 0, r, color=color, alpha=0.3)

            # Score needle
            score_theta = score / 100 * np.pi
            ax.plot([score_theta, score_theta], [0, 0.95], color='black',
                   linewidth=3, zorder=5)
            ax.plot(score_theta, 0.95, 'o', color='black', markersize=10, zorder=6)

            # Customize
            ax.set_ylim(0, 1)
            ax.set_theta_direction(-1)
            ax.set_theta_offset(np.pi)
            ax.set_xticks(np.linspace(0, np.pi, 6))
            ax.set_xticklabels(['0', '20', '40', '60', '80', '100'])
            ax.set_yticks([])
            ax.spines['polar'].set_visible(False)

            # Add score and grade text
            ax.text(np.pi/2, 0.5, f'{score:.0f}', ha='center', va='center',
                   fontsize=36, fontweight='bold')
            ax.text(np.pi/2, 0.25, f'Grade: {grade}', ha='center', va='center',
                   fontsize=18, fontweight='bold')

            plt.tight_layout()

            # Save to bytes
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                       facecolor='white')
            buf.seek(0)
            plt.close(fig)

            return buf.read()

        except Exception as e:
            logger.error(f"Error generating score gauge: {e}", exc_info=True)
            raise

    def generate_score_radar(self, category_scores: Dict[str, float]) -> bytes:
        """
        Generate radar/spider chart of category scores

        Args:
            category_scores: Dictionary of category scores

        Returns:
            PNG image as bytes
        """
        try:
            fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={'projection': 'polar'})

            # Prepare data
            categories = [
                'Property\nCondition',
                'Location\nQuality',
                'Schools',
                'Investment\nValue'
            ]

            scores = [
                float(category_scores.get('property_condition', 50)),
                float(category_scores.get('location_quality', 50)),
                float(category_scores.get('schools', 50)),
                float(category_scores.get('investment_value', 50))
            ]

            # Number of categories
            num_vars = len(categories)

            # Compute angle for each axis
            angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()

            # Complete the circle
            scores += scores[:1]
            angles += angles[:1]

            # Plot
            ax.plot(angles, scores, 'o-', linewidth=2, color=self.colors['primary'])
            ax.fill(angles, scores, alpha=0.25, color=self.colors['primary'])

            # Fix axis
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(categories, fontsize=11)
            ax.set_ylim(0, 100)
            ax.set_yticks([20, 40, 60, 80, 100])
            ax.set_yticklabels(['20', '40', '60', '80', '100'], fontsize=9)
            ax.grid(True, alpha=0.3)

            plt.title('Category Score Overview', fontsize=14, fontweight='bold', pad=20)
            plt.tight_layout()

            # Save to bytes
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            buf.seek(0)
            plt.close(fig)

            return buf.read()

        except Exception as e:
            logger.error(f"Error generating radar chart: {e}", exc_info=True)
            raise

    def generate_sub_scores_chart(
        self,
        sub_scores: Dict[str, float],
        category_name: str
    ) -> bytes:
        """
        Generate bar chart for sub-category scores

        Args:
            sub_scores: Dictionary of sub-category scores
            category_name: Name of main category

        Returns:
            PNG image as bytes
        """
        try:
            if not sub_scores:
                return None

            fig, ax = plt.subplots(figsize=(8, 5))

            # Prepare data
            labels = [k.replace('_', ' ').title() for k in sub_scores.keys()]
            scores = [float(v) for v in sub_scores.values()]

            # Create bar chart
            bars = ax.bar(labels, scores, color=self.colors['info'], alpha=0.8)

            # Customize
            ax.set_ylabel('Score (0-100)', fontsize=11, fontweight='bold')
            ax.set_title(f'{category_name} - Detailed Breakdown',
                        fontsize=13, fontweight='bold')
            ax.set_ylim(0, 100)

            # Add score labels on bars
            for bar, score in zip(bars, scores):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + 2,
                       f'{score:.0f}',
                       ha='center', va='bottom', fontsize=10, fontweight='bold')

            ax.grid(axis='y', alpha=0.3)
            plt.xticks(rotation=15, ha='right')
            plt.tight_layout()

            # Save to bytes
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            buf.seek(0)
            plt.close(fig)

            return buf.read()

        except Exception as e:
            logger.error(f"Error generating sub-scores chart: {e}", exc_info=True)
            return None
