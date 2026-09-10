from types import SimpleNamespace

from tools import pdf_reader


class FakePdf:
    def __init__(self, pages):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_digital_pdf_text_extraction(monkeypatch, tmp_path):
    pdf_path = tmp_path / "case.pdf"
    pdf_path.write_bytes(b"%PDF-test")
    extracted = " ".join(["policy"] * 35)
    monkeypatch.setattr(
        pdf_reader.pdfplumber,
        "open",
        lambda path: FakePdf([SimpleNamespace(extract_text=lambda: extracted)]),
    )

    assert pdf_reader.extract_text_from_pdf(str(pdf_path)) == extracted


def test_ocr_falls_back_to_english_when_hindi_data_is_missing(monkeypatch, tmp_path):
    pdf_path = tmp_path / "scan.pdf"
    pdf_path.write_bytes(b"%PDF-test")
    monkeypatch.setattr(pdf_reader.pdfplumber, "open", lambda path: FakePdf([]))
    monkeypatch.setattr(pdf_reader, "convert_from_path", lambda path, dpi: ["image"])
    monkeypatch.setattr(pdf_reader.pytesseract, "get_languages", lambda config: ["eng"])
    monkeypatch.setattr(
        pdf_reader.pytesseract,
        "image_to_string",
        lambda image, lang, config: "English OCR text from the scanned document.",
    )

    result = pdf_reader.extract_text_from_pdf(str(pdf_path))

    assert "English OCR text" in result
