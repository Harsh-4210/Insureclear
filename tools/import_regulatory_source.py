"""Explicit official-source import; downloaded candidates do not auto-activate rules."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.regulatory_registry import validate_official_url

MAX_DOWNLOAD_BYTES = 12_000_000


class OfficialRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_official_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_official_pdf(url: str, *, opener=None, max_bytes: int = MAX_DOWNLOAD_BYTES) -> bytes:
    validate_official_url(url)
    if not 0 < max_bytes <= MAX_DOWNLOAD_BYTES:
        raise ValueError("Invalid official-source download size limit")
    opener = opener or urllib.request.build_opener(OfficialRedirectHandler())
    with opener.open(url, timeout=25) as response:
        validate_official_url(response.geturl())
        declared = response.headers.get("Content-Length")
        if declared and int(declared) > max_bytes:
            raise ValueError("Official PDF exceeds download size limit")
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes or not data.startswith(b"%PDF-"):
        raise ValueError("Invalid or oversized official PDF")
    return data


def import_source(url: str, source_id: str, output_dir: Path) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", source_id):
        raise ValueError("Invalid source ID")
    data = download_official_pdf(url)
    output_dir = Path(output_dir)
    target = output_dir / source_id
    target.mkdir(parents=True, exist_ok=False)
    pdf_path = target / "source.pdf"
    pdf_path.write_bytes(data)
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        pages = [{"page": i + 1, "text": page.extract_text() or ""} for i, page in enumerate(pdf.pages)]
    text = json.dumps(pages, indent=2, ensure_ascii=False).encode("utf-8")
    (target / "source.pages.json").write_bytes(text)
    (target / "candidate.json").write_text(json.dumps({"id": source_id, "official_url": url, "retrieved_at": datetime.now(timezone.utc).isoformat(), "artifact_sha256": hashlib.sha256(data).hexdigest(), "text_sha256": hashlib.sha256(text).hexdigest(), "pages": len(pages), "status": "candidate_requires_clause_curation", "applicability_status": "requires_review"}, indent=2), encoding="utf-8")
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--id", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/regulatory/candidates"))
    args = parser.parse_args()
    print(import_source(args.url, args.id, args.output_dir))


if __name__ == "__main__":
    main()
