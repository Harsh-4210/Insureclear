# OCR Setup

InsureClear first tries digital text extraction with `pdfplumber`. If the text
is missing or too short, it renders the PDF with Poppler and runs Tesseract OCR.

## Windows

1. Install [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki).
2. Install [Poppler for Windows](https://github.com/oschwartz10612/poppler-windows/releases).
3. Add the Tesseract and Poppler `bin` directories to `PATH`.
4. Confirm the tools:

```powershell
tesseract --version
pdftoppm -h
```

For Hindi documents, install `hin.traineddata` into Tesseract's `tessdata`
directory. The reader uses `eng+hin` when Hindi data is available and falls back
to English-only OCR when it is not.

## Ubuntu/Debian

```bash
sudo apt-get update
sudo apt-get install -y poppler-utils tesseract-ocr tesseract-ocr-hin
```

## Docker

The repository `Dockerfile` installs Poppler, English Tesseract, and Hindi
Tesseract data automatically.

## Troubleshooting

- `PDFInfoNotInstalledError`: Poppler is missing or not on `PATH`.
- `TesseractNotFoundError`: Tesseract is missing or not on `PATH`.
- Hindi text is poor: verify `hin.traineddata` with
  `tesseract --list-langs`.
- A digital PDF with fewer than 30 extracted words is intentionally sent through
  OCR; this threshold avoids silently passing nearly empty scans to the agents.
