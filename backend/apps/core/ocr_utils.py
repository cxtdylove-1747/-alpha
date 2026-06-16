from __future__ import annotations

from typing import Optional


def _ocr_with_tesseract(file_path: str) -> Optional[str]:
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except Exception:
        return None

    try:
        pages = convert_from_path(file_path, dpi=180, first_page=1, last_page=8)
    except Exception:
        return None

    texts = []
    for image in pages:
        try:
            text = pytesseract.image_to_string(image, lang="chi_sim+eng")
        except Exception:
            text = ""
        if text and text.strip():
            texts.append(text.strip())
    return "\n".join(texts).strip() or None


def _ocr_pages_with_rapidocr(file_path: str, max_pages: int = 100, target_pages: list[int] | None = None) -> list[dict]:
    try:
        import pypdfium2 as pdfium
        from rapidocr_onnxruntime import RapidOCR
    except Exception:
        return []

    try:
        doc = pdfium.PdfDocument(file_path)
    except Exception:
        return []

    engine = RapidOCR()
    page_count = min(len(doc), max_pages)
    if target_pages:
        selected = sorted({p for p in target_pages if 1 <= int(p) <= page_count})
    else:
        selected = list(range(1, page_count + 1))
    pages = []
    for page_no in selected:
        text = ""
        page = None
        bitmap = None
        try:
            page = doc[page_no - 1]
            bitmap = page.render(scale=2)
            image = bitmap.to_pil()
            result, _ = engine(image)
            if result:
                line_texts = []
                for item in result:
                    if isinstance(item, (list, tuple)) and len(item) >= 2 and item[1]:
                        line_texts.append(str(item[1]).strip())
                text = " ".join([line for line in line_texts if line]).strip()
        except Exception:
            text = ""
        finally:
            try:
                if bitmap is not None:
                    bitmap.close()
            except Exception:
                pass
            try:
                if page is not None:
                    page.close()
            except Exception:
                pass
        pages.append({"page": page_no, "text": text})
    try:
        doc.close()
    except Exception:
        pass
    return pages


def _ocr_with_rapidocr(file_path: str) -> Optional[str]:
    pages = _ocr_pages_with_rapidocr(file_path, max_pages=8)
    text = "\n".join((item.get("text") or "") for item in pages if (item.get("text") or "").strip()).strip()
    return text or None


def extract_pages_via_ocr(file_path: str, max_pages: int = 100, target_pages: list[int] | None = None) -> list[dict]:
    """Extract OCR text for each PDF page, used as a fallback when native parsing is incomplete."""
    pages = _ocr_pages_with_rapidocr(file_path, max_pages=max_pages, target_pages=target_pages)
    if pages and any((item.get("text") or "").strip() for item in pages):
        return pages
    text = _ocr_with_tesseract(file_path)
    if not text:
        return []
    return [{"page": 1, "text": text.strip()}]


def extract_text_via_ocr(file_path: str) -> Optional[str]:
    """
    Optional OCR hook for scanned PDFs.
    Returns None when OCR runtime/dependencies are unavailable.
    """
    text = _ocr_with_tesseract(file_path)
    if text:
        return text
    return _ocr_with_rapidocr(file_path)

