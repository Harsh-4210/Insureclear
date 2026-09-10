"""
PDF Reader Tool
Handles both digital PDFs and scanned image PDFs (common for Indian documents).
Falls back to OCR when text extraction returns poor quality.
"""

import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from pathlib import Path


_OCR_LANGUAGES = ("eng+hin", "eng")


def _is_text_quality_good(text: str, min_words: int = 30) -> bool:
    """Check if extracted text is usable — scanned PDFs often return garbled output."""
    if not text:
        return False
    words = text.split()
    # Scanned PDFs often have very few recognisable words despite large character count
    return len(words) >= min_words


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from a PDF file.
    Strategy:
    1. Try pdfplumber (fast, works for digital PDFs)
    2. If output is poor, fall back to pytesseract OCR (for scanned/photo PDFs)
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # Step 1: Try digital extraction
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    pages.append(page_text)
            text = "\n\n".join(pages)
    except Exception as e:
        print(f"[pdf_reader] pdfplumber failed: {e}. Trying OCR...")

    if _is_text_quality_good(text):
        print(f"[pdf_reader] Digital extraction succeeded ({len(text.split())} words)")
        return text.strip()

    # Step 2: Fall back to OCR
    print("[pdf_reader] Digital extraction poor — running OCR (this may take a moment)...")
    try:
        images = convert_from_path(pdf_path, dpi=300)
        ocr_pages = []
        available_languages = None

        try:
            available_languages = set(pytesseract.get_languages(config=""))
        except Exception:
            available_languages = None

        if available_languages is not None and "hin" not in available_languages:
            languages_to_try = ("eng",)
        else:
            languages_to_try = _OCR_LANGUAGES

        for i, image in enumerate(images):
            page_text = ""
            for language in languages_to_try:
                try:
                    # Use English + Hindi OCR when available; fall back to English-only.
                    page_text = pytesseract.image_to_string(
                        image,
                        lang=language,
                        config="--psm 6"  # Assume uniform block of text
                    )
                except Exception as e:
                    if language == languages_to_try[-1]:
                        raise e
                    page_text = ""

                if page_text.strip():
                    break

            if page_text.strip():
                ocr_pages.append(page_text)
            print(f"[pdf_reader] OCR page {i+1}/{len(images)} done")
        text = "\n\n".join(ocr_pages)
        print(f"[pdf_reader] OCR extraction done ({len(text.split())} words)")
        return text.strip()
    except Exception as e:
        raise RuntimeError(f"Both PDF extraction methods failed: {e}")


def extract_text_safe(pdf_path: str) -> str:
    """Wrapper that returns empty string instead of raising — for optional inputs."""
    try:
        return extract_text_from_pdf(pdf_path)
    except Exception as e:
        print(f"[pdf_reader] Warning: Could not read {pdf_path}: {e}")
        return ""
