"""
PDF Processor - Extract text from PDF documents using PyMuPDF
"""
import logging
from pathlib import Path
from typing import Optional
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# Minimum characters to consider text extraction successful
MIN_TEXT_CHARS = 100


class PDFProcessor:
    """
    Extracts text content from PDF documents.

    Primary: Direct text extraction (works for most inspection/HOA docs)
    Fallback: Could add OCR for scanned PDFs if needed
    """

    def __init__(self):
        pass

    def extract_text(self, pdf_path: Path) -> str:
        """
        Extract text from a PDF file.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Extracted text content

        Raises:
            ValueError: If PDF cannot be processed
        """
        if not pdf_path.exists():
            raise ValueError(f"PDF file not found: {pdf_path}")

        try:
            doc = fitz.open(pdf_path)
            text_parts = []

            for page_num, page in enumerate(doc, 1):
                page_text = page.get_text()
                if page_text.strip():
                    text_parts.append(f"--- Page {page_num} ---\n{page_text}")

            doc.close()

            full_text = "\n\n".join(text_parts)

            if len(full_text) < MIN_TEXT_CHARS:
                logger.warning(
                    f"PDF text extraction yielded only {len(full_text)} chars. "
                    f"This may be a scanned PDF: {pdf_path}"
                )

            logger.info(f"Extracted {len(full_text)} chars from {pdf_path.name} ({len(text_parts)} pages)")
            return full_text

        except Exception as e:
            logger.error(f"Failed to extract text from PDF: {e}")
            raise ValueError(f"Failed to process PDF: {e}")

    def is_text_based(self, pdf_path: Path) -> bool:
        """
        Check if PDF contains extractable text (not just scanned images).

        Args:
            pdf_path: Path to the PDF file

        Returns:
            True if PDF has sufficient text content
        """
        try:
            text = self.extract_text(pdf_path)
            return len(text) >= MIN_TEXT_CHARS
        except Exception:
            return False

    def get_page_count(self, pdf_path: Path) -> int:
        """Get number of pages in PDF."""
        try:
            doc = fitz.open(pdf_path)
            count = len(doc)
            doc.close()
            return count
        except Exception:
            return 0

    def extract_first_n_chars(self, pdf_path: Path, n: int = 2000) -> str:
        """
        Extract first N characters from PDF for classification.

        Args:
            pdf_path: Path to the PDF file
            n: Maximum characters to extract

        Returns:
            First N characters of text
        """
        text = self.extract_text(pdf_path)
        return text[:n]


# Global instance
_processor: Optional[PDFProcessor] = None


def get_pdf_processor() -> PDFProcessor:
    """Get singleton PDF processor instance."""
    global _processor
    if _processor is None:
        _processor = PDFProcessor()
    return _processor
