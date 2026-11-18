"""Extract plain text from uploaded PDF, DOCX and TXT files.

Files are parsed from memory. Magic bytes are checked so a renamed file is rejected,
and DOCX archives are checked for decompression bombs before parsing. PDF pages without a
text layer (scans) are passed to an optional OCR callable, which receives them as JPEG bytes.
"""

import io
import re
import zipfile
from collections.abc import Callable

import fitz  # PyMuPDF
from docx import Document as DocxDocument

from ..utils import ApiError

MAX_PDF_PAGES = 300
# A page with fewer characters than this has no usable text layer and is treated as a scan.
MIN_TEXT_CHARS_PER_PAGE = 20
MAX_DOCX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def extract_text(
    data: bytes,
    extension: str,
    max_chars: int,
    ocr: Callable[[list[bytes]], list[str]] | None = None,
    ocr_dpi: int = 150,
    ocr_batch_pages: int = 8,
    ocr_max_pages: int = 40,
) -> str:
    if not data:
        raise ApiError("The uploaded file is empty.")

    if extension == "pdf":
        raw = _from_pdf(data, ocr, ocr_dpi, ocr_batch_pages, ocr_max_pages)
    elif extension == "docx":
        raw = _from_docx(data)
    elif extension == "txt":
        raw = _from_txt(data)
    else:
        raise ApiError("Unsupported file type. Upload a PDF, TXT or DOCX file.")

    text = _normalise(raw)
    if not text:
        raise ApiError("No readable text was found in this file.")
    if len(text) > max_chars:
        raise ApiError(
            f"This document has {len(text):,} characters of text. The maximum is {max_chars:,}. "
            "Split it into smaller files and upload them separately."
        )
    return text


def _from_pdf(data: bytes, ocr, ocr_dpi: int, ocr_batch_pages: int, ocr_max_pages: int) -> str:
    if not data.startswith(b"%PDF"):
        raise ApiError("This file does not look like a valid PDF.")
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:  # PyMuPDF raises a variety of errors for corrupt files
        raise ApiError("Could not open this PDF. It may be corrupted.") from exc
    with doc:
        if doc.needs_pass or doc.is_encrypted:
            raise ApiError("Password-protected PDFs are not supported.")
        if doc.page_count > MAX_PDF_PAGES:
            raise ApiError(f"This PDF has {doc.page_count} pages. The maximum is {MAX_PDF_PAGES}.")

        pages = [page.get_text("text") for page in doc]
        scanned = [i for i, text in enumerate(pages) if len(text.strip()) < MIN_TEXT_CHARS_PER_PAGE]
        if not scanned:
            return "\n\n".join(pages)

        if ocr is None:
            if len(scanned) == len(pages):
                raise ApiError(
                    "This PDF has no text layer. Scanned PDFs need OCR, which requires AI features "
                    "to be configured."
                )
            return "\n\n".join(pages)

        if len(scanned) > ocr_max_pages:
            raise ApiError(
                f"This PDF has {len(scanned)} pages without text. OCR supports up to "
                f"{ocr_max_pages} scanned pages per file."
            )
        for start in range(0, len(scanned), ocr_batch_pages):
            batch = scanned[start:start + ocr_batch_pages]
            images = [doc[i].get_pixmap(dpi=ocr_dpi).tobytes("jpeg", jpg_quality=85) for i in batch]
            for index, text in zip(batch, ocr(images)):
                pages[index] = text
        return "\n\n".join(pages)


def _from_docx(data: bytes) -> str:
    if not data.startswith(b"PK"):
        raise ApiError("This file does not look like a valid DOCX document.")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if "word/document.xml" not in archive.namelist():
                raise ApiError("This file does not look like a valid DOCX document.")
            total = sum(info.file_size for info in archive.infolist())
            if total > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise ApiError("This DOCX file is too large once decompressed.")
        document = DocxDocument(io.BytesIO(data))
    except ApiError:
        raise
    except Exception as exc:
        raise ApiError("Could not read this DOCX file. It may be corrupted.") from exc

    parts = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(parts)


def _from_txt(data: bytes) -> str:
    if b"\x00" in data[:4096]:
        raise ApiError("This text file contains binary data and cannot be read.")
    return data.decode("utf-8-sig", errors="replace")


def _normalise(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL_CHARS.sub("", text)
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
