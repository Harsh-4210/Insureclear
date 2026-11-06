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
    monkeypatch.setattr(pdf_reader, "convert_from_path", lambda path, **kwargs: ["image"])
    monkeypatch.setattr(pdf_reader, "pdfinfo_from_path", lambda *args, **kwargs: {"Pages": 1})
    monkeypatch.setattr(pdf_reader.pytesseract, "get_languages", lambda config: ["eng"])
    monkeypatch.setattr(
        pdf_reader.pytesseract,
        "image_to_string",
        lambda image, lang, config, **kwargs: "English OCR text from the scanned document.",
    )

    result = pdf_reader.extract_text_from_pdf(str(pdf_path))

    assert "English OCR text" in result


def test_pdf_page_cap_fails_before_extraction(monkeypatch, tmp_path):
    import pytest
    pdf_path = tmp_path / "many.pdf"; pdf_path.write_bytes(b"%PDF-test")
    monkeypatch.setenv("INSURECLEAR_MAX_PDF_PAGES", "2")
    monkeypatch.setattr(pdf_reader.pdfplumber, "open", lambda path: FakePdf([SimpleNamespace(extract_text=lambda: pytest.fail("Over-limit page extracted"))] * 3))
    with pytest.raises(ValueError, match="page limit"): pdf_reader.extract_text_from_pdf(str(pdf_path))


def test_ocr_renders_only_one_bounded_page_at_a_time(monkeypatch, tmp_path):
    path = tmp_path / "scan.pdf"; path.write_bytes(b"%PDF-test")
    monkeypatch.setattr(pdf_reader.pdfplumber, "open", lambda path: FakePdf([]))
    monkeypatch.setattr(pdf_reader, "pdfinfo_from_path", lambda *args, **kwargs: {"Pages": 2}, raising=False)
    calls = []
    def convert(path, **kwargs):
        calls.append(kwargs)
        return ["image"]
    monkeypatch.setattr(pdf_reader, "convert_from_path", convert)
    monkeypatch.setattr(pdf_reader.pytesseract, "get_languages", lambda **kwargs: ["eng"])
    monkeypatch.setattr(pdf_reader.pytesseract, "image_to_string", lambda *args, **kwargs: "Covered hospital treatment " * 35)
    assert "Covered" in pdf_reader.extract_text_from_pdf(str(path))
    assert [call["first_page"] for call in calls] == [1, 2]
    assert all(call["first_page"] == call["last_page"] and call["timeout"] == 30 and call["size"] == 2500 for call in calls)


def test_extracted_text_limit_is_explicit_not_truncation(monkeypatch, tmp_path):
    import pytest
    path = tmp_path / "long.pdf"; path.write_bytes(b"%PDF-test")
    monkeypatch.setenv("INSURECLEAR_MAX_TEXT_CHARS", "100")
    monkeypatch.setattr(pdf_reader.pdfplumber, "open", lambda path: FakePdf([SimpleNamespace(extract_text=lambda: "policy " * 100)]))
    with pytest.raises(ValueError, match="text limit"): pdf_reader.extract_text_from_pdf(str(path))
