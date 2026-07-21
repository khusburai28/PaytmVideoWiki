import fitz  # PyMuPDF
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

MIN_PAGE_TEXT_CHARS = 40   # below this, a page is treated as scanned/drawing-only and OCR'd via Gemini vision
MIN_CHUNK_CHARS = 150      # merge short pages forward, mirrors VideoProcessor.merge_small_segments


class PDFProcessor:
    """Extracts per-page text from PDFs. Pages with little/no extractable text
    (scanned pages, P&ID-style drawings) fall back to Gemini vision for OCR + description."""

    def __init__(self, gemini_client, status_store: Optional[Dict] = None):
        self.gemini_client = gemini_client
        self.status_store = status_store if status_store is not None else {}

    def _set_status(self, document_id: str, status: str, progress: int, message: str):
        self.status_store[document_id] = {"status": status, "progress": progress, "message": message}

    def process(self, file_path: str, document_id: str) -> Tuple[List[Dict], Dict]:
        self._set_status(document_id, "extracting_text", 20, "Extracting text from PDF pages...")

        doc = fitz.open(file_path)
        page_texts = []

        try:
            for page_index in range(len(doc)):
                page = doc[page_index]
                text = page.get_text().strip()

                if len(text) < MIN_PAGE_TEXT_CHARS:
                    self._set_status(
                        document_id, "ocr_scanning", 40,
                        f"Reading scanned page {page_index + 1} of {len(doc)}..."
                    )
                    text = self._describe_scanned_page(page, page_index) or text

                page_texts.append(text)
        finally:
            doc.close()

        self._set_status(document_id, "processing_segments", 70, "Merging document chunks...")
        segments = self._merge_pages(page_texts)

        self._set_status(document_id, "completed", 100, "PDF processing completed successfully!")
        return segments, {"duration": None, "page_count": len(page_texts)}

    def _describe_scanned_page(self, page, page_index: int) -> str:
        try:
            pixmap = page.get_pixmap(dpi=150)
            image_bytes = pixmap.tobytes("png")
            return self.gemini_client.describe_image(
                image_bytes=image_bytes,
                instruction=(
                    "Transcribe all readable text on this document page (OCR), preserving labels, "
                    "tags, and numbers exactly. Then briefly describe any diagrams, tables, or "
                    "drawings present (e.g. equipment layout, P&ID symbols)."
                )
            )
        except Exception as e:
            logger.warning(f"Failed to OCR page {page_index + 1} via Gemini vision: {e}")
            return ""

    def _merge_pages(self, page_texts: List[str]) -> List[Dict]:
        segments = []
        buffer_text = ""
        buffer_start_page = None

        for page_index, text in enumerate(page_texts):
            page_number = page_index + 1
            if not text:
                continue
            if buffer_start_page is None:
                buffer_start_page = page_number
            buffer_text = f"{buffer_text}\n\n[Page {page_number}] {text}".strip()

            if len(buffer_text) >= MIN_CHUNK_CHARS:
                segments.append({
                    "text": buffer_text,
                    "page_number": buffer_start_page,
                    "confidence": 1.0
                })
                buffer_text = ""
                buffer_start_page = None

        if buffer_text:
            segments.append({
                "text": buffer_text,
                "page_number": buffer_start_page or 1,
                "confidence": 1.0
            })

        if not segments:
            segments.append({
                "text": "(No extractable text found in this PDF.)",
                "page_number": 1,
                "confidence": 0.0
            })

        return segments
