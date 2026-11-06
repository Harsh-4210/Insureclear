"""Bounded digital extraction and page-at-a-time OCR for private case PDFs."""
import os
from pathlib import Path
import pdfplumber
import pytesseract
from pdf2image import convert_from_path, pdfinfo_from_path

_OCR_LANGUAGES = ("eng+hin", "eng")


class PdfLimitError(ValueError):
    pass


def _is_text_quality_good(text: str, min_words: int = 30) -> bool:
    return bool(text) and len(text.split()) >= min_words


def extract_text_from_pdf(pdf_path: str, control=None) -> str:
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError("PDF input is unavailable")
    maximum_pages = int(os.getenv("INSURECLEAR_MAX_PDF_PAGES", "200"))
    maximum_ocr = int(os.getenv("INSURECLEAR_MAX_OCR_PAGES", "40"))
    maximum_text = int(os.getenv("INSURECLEAR_MAX_TEXT_CHARS", "500000"))
    if min(maximum_pages, maximum_ocr, maximum_text) < 1:
        raise ValueError("PDF extraction limits must be positive")
    check = control or (lambda: None)
    check()
    pages, length = [], 0
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if len(pdf.pages) > maximum_pages:
                raise PdfLimitError("PDF page limit exceeded; split or review the document")
            for page in pdf.pages:
                check()
                text = page.extract_text() or ""
                length += len(text) + 2
                if length > maximum_text:
                    raise PdfLimitError("Extracted text limit exceeded; no text was silently truncated")
                pages.append(text)
    except PdfLimitError:
        raise
    except Exception as error:
        # Preserve cooperative cancellation rather than treating it as an OCR failure.
        from tools.runtime_control import PipelineCancelled, PipelineTimedOut, PipelineBudgetExceeded
        if isinstance(error, (PipelineCancelled, PipelineTimedOut, PipelineBudgetExceeded)):
            raise
        print(f"[pdf_reader] Digital extraction failed ({type(error).__name__}); trying bounded OCR")
    text = "\n\n".join(pages)
    if _is_text_quality_good(text):
        return text.strip()

    check()
    try:
        count = int(pdfinfo_from_path(pdf_path, timeout=30)["Pages"])
        if not 1 <= count <= min(maximum_pages, maximum_ocr):
            raise PdfLimitError("OCR page limit exceeded or PDF has no pages")
        try:
            languages = set(pytesseract.get_languages(config=""))
        except Exception:
            languages = None
        options = ("eng",) if languages is not None and "hin" not in languages else _OCR_LANGUAGES
        pages, length = [], 0
        for page_number in range(1, count + 1):
            check()
            images = convert_from_path(pdf_path, dpi=300, first_page=page_number, last_page=page_number, thread_count=1, grayscale=True, size=2500, timeout=30)
            try:
                if len(images) != 1:
                    raise RuntimeError("OCR renderer did not return exactly one page")
                text = ""
                for language in options:
                    check()
                    try:
                        text = pytesseract.image_to_string(images[0], lang=language, config="--psm 6", timeout=30)
                    except Exception:
                        if language == options[-1]: raise
                    if text.strip(): break
                length += len(text) + 2
                if length > maximum_text:
                    raise PdfLimitError("Extracted text limit exceeded; no text was silently truncated")
                pages.append(text)
            finally:
                for image in images:
                    close = getattr(image, "close", None)
                    if close: close()
        return "\n\n".join(pages).strip()
    except PdfLimitError:
        raise
    except Exception as error:
        from tools.runtime_control import PipelineCancelled, PipelineTimedOut, PipelineBudgetExceeded
        if isinstance(error, (PipelineCancelled, PipelineTimedOut, PipelineBudgetExceeded)):
            raise
        raise RuntimeError("Bounded PDF/OCR extraction failed; check the input and local OCR dependencies") from None


def extract_text_safe(pdf_path: str) -> str:
    """Optional-input compatibility wrapper; never prints source paths/errors."""
    try:
        return extract_text_from_pdf(pdf_path)
    except Exception as error:
        print(f"[pdf_reader] Optional input unavailable ({type(error).__name__})")
        return ""
