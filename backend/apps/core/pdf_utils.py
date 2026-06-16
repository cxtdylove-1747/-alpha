from pypdf import PdfReader

from .ocr_utils import extract_pages_via_ocr, extract_text_via_ocr


def _extract_with_pymupdf(file_path: str) -> list[dict]:
    try:
        import fitz
    except Exception:
        return []

    pages = []
    try:
        doc = fitz.open(file_path)
        for idx, page in enumerate(doc, start=1):
            text = (page.get_text("text") or "").replace("\x00", "").strip()
            pages.append({"page": idx, "text": text})
    except Exception:
        return []
    return pages


def _clean_text(text: str) -> str:
    return (text or "").replace("\x00", "").strip()


def _to_page_map(rows: list[dict]) -> dict[int, str]:
    data = {}
    for item in rows or []:
        page_no = int(item.get("page", 0) or 0)
        if page_no <= 0:
            continue
        data[page_no] = _clean_text(item.get("text", ""))
    return data


def parse_pdf(file_path: str) -> dict:
    pypdf_pages = []
    try:
        reader = PdfReader(file_path)
        for idx, page in enumerate(reader.pages, start=1):
            text = _clean_text(page.extract_text() or "")
            pypdf_pages.append({"page": idx, "text": text})
    except Exception:
        pypdf_pages = []

    pymupdf_pages = _extract_with_pymupdf(file_path)

    page_count = max(len(pypdf_pages), len(pymupdf_pages))
    if page_count > 100:
        page_count = 100

    pypdf_map = _to_page_map(pypdf_pages)
    pymupdf_map = _to_page_map(pymupdf_pages)

    pages = []
    for page_no in range(1, page_count + 1):
        text = pypdf_map.get(page_no) or pymupdf_map.get(page_no) or ""
        pages.append({"page": page_no, "text": text})

    # Fill empty pages with OCR output when native extraction is missing.
    empty_pages = [item for item in pages if not (item.get("text") or "").strip()]
    non_empty_count = len(pages) - len(empty_pages)
    native_ratio = (non_empty_count / len(pages)) if pages else 0
    # OCR is expensive; only run when native extraction coverage is low.
    if empty_pages and native_ratio < 0.8:
        target_page_numbers = [item.get("page", 0) for item in empty_pages if int(item.get("page", 0) or 0) > 0]
        # If native parsing failed for all pages, OCR the whole document; otherwise OCR only missing pages.
        ocr_targets = None if len(empty_pages) == len(pages) else target_page_numbers
        ocr_pages = extract_pages_via_ocr(file_path, max_pages=page_count or 100, target_pages=ocr_targets)
        ocr_map = _to_page_map(ocr_pages)
        for item in pages:
            if not (item.get("text") or "").strip():
                item["text"] = ocr_map.get(item["page"], "")

    if not any(item["text"] for item in pages):
        ocr_text = extract_text_via_ocr(file_path) or ""
        if ocr_text.strip():
            pages = [{"page": 1, "text": ocr_text.strip()}]

    return {
        "page_count": len(pages),
        "pages": pages,
        "text": "\n".join(item["text"] for item in pages if item["text"]).strip(),
    }


def extract_pdf_text(file_path: str) -> str:
    parsed = parse_pdf(file_path)
    return parsed["text"]


