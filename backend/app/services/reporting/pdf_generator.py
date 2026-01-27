"""
PDF report generation using ReportLab
"""
import io
import logging
from datetime import datetime
from typing import Dict, Any, List
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    Image, PageBreak, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from app.services.reporting.visualization import ChartGenerator

logger = logging.getLogger(__name__)


class PDFReportGenerator:
    """
    Generate comprehensive PDF reports for property analysis
    """

    def __init__(self):
        self.chart_generator = ChartGenerator()
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Create custom paragraph styles"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1976d2'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))

        # Section header
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#1976d2'),
            spaceBefore=20,
            spaceAfter=12,
            borderWidth=2,
            borderColor=colors.HexColor('#1976d2'),
            borderPadding=8,
            backColor=colors.HexColor('#e3f2fd')
        ))

        # Grade style
        self.styles.add(ParagraphStyle(
            name='Grade',
            parent=self.styles['Normal'],
            fontSize=48,
            textColor=colors.HexColor('#4caf50'),
            alignment=TA_CENTER,
            spaceAfter=10
        ))

    def generate_report(self, analysis_result: Dict[str, Any]) -> bytes:
        """
        Generate complete PDF report

        Args:
            analysis_result: Analysis results from orchestrator

        Returns:
            PDF as bytes
        """
        try:
            logger.info("Generating PDF report")

            # Create PDF in memory
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                rightMargin=0.75*inch,
                leftMargin=0.75*inch,
                topMargin=1*inch,
                bottomMargin=0.75*inch
            )

            # Build story (content)
            story = []

            # Cover page
            story.extend(self._create_cover_page(analysis_result))
            story.append(PageBreak())

            # Executive summary
            story.extend(self._create_executive_summary(analysis_result))
            story.append(PageBreak())

            # Score breakdown
            story.extend(self._create_score_breakdown(analysis_result))
            story.append(PageBreak())

            # Detailed analysis for each category
            story.extend(self._create_detailed_analysis(analysis_result))

            # Build PDF
            doc.build(story)

            # Get PDF bytes
            pdf_bytes = buffer.getvalue()
            buffer.close()

            logger.info(f"PDF report generated successfully ({len(pdf_bytes)} bytes)")
            return pdf_bytes

        except Exception as e:
            logger.error(f"Error generating PDF report: {e}", exc_info=True)
            raise

    def _create_cover_page(self, result: Dict[str, Any]) -> List:
        """Create cover page"""
        elements = []

        # Title
        elements.append(Spacer(1, 1.5*inch))
        elements.append(Paragraph(
            "PROPERTY ANALYSIS REPORT",
            self.styles['CustomTitle']
        ))

        elements.append(Spacer(1, 0.5*inch))

        # Overall grade in large font
        grade = result.get('overall_grade', 'N/A')
        elements.append(Paragraph(
            f"Grade: {grade}",
            self.styles['Grade']
        ))

        # Overall score
        score = float(result.get('overall_score', 0))
        elements.append(Paragraph(
            f"Overall Score: {score:.0f}/100",
            self.styles['Heading1']
        ))

        elements.append(Spacer(1, 0.5*inch))

        # Property address
        property_data = result.get('property_data', {})
        address = property_data.get('address', 'Unknown')
        elements.append(Paragraph(
            f"<b>Property Address:</b><br/>{address}",
            self.styles['Normal']
        ))

        elements.append(Spacer(1, 0.3*inch))

        # Analysis date
        analyzed_at = result.get('analyzed_at', datetime.now().isoformat())
        try:
            date_obj = datetime.fromisoformat(analyzed_at.replace('Z', '+00:00'))
            date_str = date_obj.strftime('%B %d, %Y')
        except:
            date_str = analyzed_at

        elements.append(Paragraph(
            f"<b>Analysis Date:</b> {date_str}",
            self.styles['Normal']
        ))

        # Confidence level
        confidence = result.get('confidence_level', 'medium')
        elements.append(Paragraph(
            f"<b>Confidence Level:</b> {confidence.title()}",
            self.styles['Normal']
        ))

        return elements

    def _create_executive_summary(self, result: Dict[str, Any]) -> List:
        """Create executive summary section"""
        elements = []

        elements.append(Paragraph("EXECUTIVE SUMMARY", self.styles['SectionHeader']))
        elements.append(Spacer(1, 0.2*inch))

        # Interpretation
        interpretation = result.get('interpretation', {})
        summary = interpretation.get('summary', 'Property Analysis Complete')
        description = interpretation.get('description', '')
        recommendation = interpretation.get('recommendation', '')

        elements.append(Paragraph(f"<b>{summary}</b>", self.styles['Heading3']))
        elements.append(Spacer(1, 0.1*inch))
        elements.append(Paragraph(description, self.styles['Normal']))
        elements.append(Spacer(1, 0.15*inch))

        # Add score gauge chart
        try:
            score = float(result.get('overall_score', 0))
            grade = result.get('overall_grade', 'C')
            gauge_img = self.chart_generator.generate_score_gauge(score, grade)
            img = Image(io.BytesIO(gauge_img), width=5*inch, height=3*inch)
            elements.append(img)
            elements.append(Spacer(1, 0.2*inch))
        except Exception as e:
            logger.warning(f"Could not generate gauge chart: {e}")

        # Recommendation
        elements.append(Paragraph(f"<b>Recommendation:</b>", self.styles['Heading4']))
        elements.append(Paragraph(recommendation, self.styles['Normal']))

        return elements

    def _create_score_breakdown(self, result: Dict[str, Any]) -> List:
        """Create score breakdown section"""
        elements = []

        elements.append(Paragraph("SCORE BREAKDOWN", self.styles['SectionHeader']))
        elements.append(Spacer(1, 0.2*inch))

        # Generate bar chart
        try:
            category_scores = result.get('category_scores', {})
            overall_score = float(result.get('overall_score', 0))

            chart_img = self.chart_generator.generate_score_bar_chart(
                category_scores,
                overall_score
            )
            img = Image(io.BytesIO(chart_img), width=6.5*inch, height=4*inch)
            elements.append(img)
            elements.append(Spacer(1, 0.3*inch))
        except Exception as e:
            logger.warning(f"Could not generate bar chart: {e}")

        # Create scores table
        category_names = {
            'property_condition': 'Property Condition',
            'location_quality': 'Location Quality',
            'schools': 'Schools',
            'investment_value': 'Investment Value'
        }

        weights = {
            'property_condition': '30%',
            'location_quality': '25%',
            'schools': '20%',
            'investment_value': '25%'
        }

        scores_data = [['Category', 'Weight', 'Score', 'Grade']]

        for key, name in category_names.items():
            score = float(result.get('category_scores', {}).get(key, 0))
            grade = self._score_to_grade(score)
            scores_data.append([
                name,
                weights[key],
                f'{score:.0f}/100',
                grade
            ])

        table = Table(scores_data, colWidths=[3*inch, 1*inch, 1.5*inch, 0.75*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
        ]))

        elements.append(table)

        return elements

    def _create_detailed_analysis(self, result: Dict[str, Any]) -> List:
        """Create detailed analysis sections for each category"""
        elements = []

        detailed = result.get('detailed_analysis', {})

        # Property Condition
        if 'property_condition' in detailed:
            elements.extend(self._create_category_section(
                "PROPERTY CONDITION",
                detailed['property_condition'],
                result.get('category_scores', {}).get('property_condition', 0)
            ))
            elements.append(PageBreak())

        # Location Quality
        if 'location_quality' in detailed:
            elements.extend(self._create_category_section(
                "LOCATION QUALITY",
                detailed['location_quality'],
                result.get('category_scores', {}).get('location_quality', 0)
            ))
            elements.append(PageBreak())

        # Schools
        if 'schools' in detailed:
            elements.extend(self._create_category_section(
                "SCHOOLS",
                detailed['schools'],
                result.get('category_scores', {}).get('schools', 0)
            ))
            elements.append(PageBreak())

        # Investment Value
        if 'investment_value' in detailed:
            elements.extend(self._create_category_section(
                "INVESTMENT VALUE",
                detailed['investment_value'],
                result.get('category_scores', {}).get('investment_value', 0)
            ))

        return elements

    def _create_category_section(
        self,
        title: str,
        analysis: Dict[str, Any],
        score: float
    ) -> List:
        """Create section for a single category"""
        elements = []

        # Section header
        elements.append(Paragraph(title, self.styles['SectionHeader']))
        elements.append(Spacer(1, 0.15*inch))

        # Score and grade
        grade = self._score_to_grade(score)
        elements.append(Paragraph(
            f"<b>Score:</b> {score:.0f}/100 ({grade})",
            self.styles['Heading3']
        ))
        elements.append(Spacer(1, 0.15*inch))

        # Reasoning
        reasoning = analysis.get('reasoning', 'No detailed analysis available')
        elements.append(Paragraph("<b>Analysis:</b>", self.styles['Heading4']))
        elements.append(Paragraph(reasoning, self.styles['Normal']))
        elements.append(Spacer(1, 0.15*inch))

        # Highlights/Strengths
        highlights = analysis.get('highlights', analysis.get('strengths', analysis.get('pros', [])))
        if highlights:
            elements.append(Paragraph("<b>Highlights:</b>", self.styles['Heading4']))
            for item in highlights:
                elements.append(Paragraph(f"• {item}", self.styles['Normal']))
            elements.append(Spacer(1, 0.1*inch))

        # Concerns/Limitations
        concerns = analysis.get('concerns', analysis.get('limitations', analysis.get('cons', [])))
        if concerns:
            elements.append(Paragraph("<b>Concerns:</b>", self.styles['Heading4']))
            for item in concerns:
                elements.append(Paragraph(f"• {item}", self.styles['Normal']))
            elements.append(Spacer(1, 0.1*inch))

        # Recommendations (if available)
        if 'recommendations' in analysis:
            recommendations = analysis['recommendations']
            if recommendations:
                elements.append(Paragraph("<b>Recommendations:</b>", self.styles['Heading4']))
                for item in (recommendations if isinstance(recommendations, list) else [recommendations]):
                    elements.append(Paragraph(f"• {item}", self.styles['Normal']))

        return elements

    @staticmethod
    def _score_to_grade(score: float) -> str:
        """Convert score to letter grade"""
        if score >= 90:
            return 'A'
        elif score >= 80:
            return 'B'
        elif score >= 70:
            return 'C'
        elif score >= 60:
            return 'D'
        else:
            return 'F'
