from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

from app.services.ingestion.pdf_processor import PDFProcessor
from app.services.ingestion.image_processor import ImageProcessor
from app.services.ingestion.spreadsheet_processor import SpreadsheetProcessor

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
SPREADSHEET_EXTENSIONS = {".xlsx", ".xls", ".csv"}

ALL_ALLOWED_EXTENSIONS = VIDEO_EXTENSIONS | PDF_EXTENSIONS | IMAGE_EXTENSIONS | SPREADSHEET_EXTENSIONS


def detect_document_type(filename: str) -> Optional[str]:
    ext = Path(filename).suffix.lower()
    if ext in VIDEO_EXTENSIONS:
        return "video"
    if ext in PDF_EXTENSIONS:
        return "pdf"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in SPREADSHEET_EXTENSIONS:
        return "spreadsheet"
    return None


class DocumentDispatcher:
    """Routes an uploaded file to the right type-specific processor and normalizes
    the output to (chunks, extra_metadata) regardless of format. The video path wraps
    the existing VideoProcessor unchanged - nothing about video ingestion is rewritten."""

    def __init__(self, video_processor, gemini_client):
        self.video_processor = video_processor
        # All new processors share VideoProcessor's processing_status dict so the
        # existing GET /api/status/{id} polling endpoint keeps working for every type.
        status_store = video_processor.processing_status
        self.pdf_processor = PDFProcessor(gemini_client=gemini_client, status_store=status_store)
        self.image_processor = ImageProcessor(gemini_client=gemini_client, status_store=status_store)
        self.spreadsheet_processor = SpreadsheetProcessor(gemini_client=gemini_client, status_store=status_store)

    def process(self, document_type: str, file_path: str, document_id: str) -> Tuple[List[Dict], Dict]:
        """Returns (chunks, extra_metadata). extra_metadata always includes a 'duration'
        key (None for non-video types) so callers can treat every type uniformly."""
        if document_type == "video":
            segments, duration = self.video_processor.process_video(file_path, document_id)
            return segments, {"duration": duration}

        if document_type == "pdf":
            return self.pdf_processor.process(file_path, document_id)

        if document_type == "image":
            return self.image_processor.process(file_path, document_id)

        if document_type == "spreadsheet":
            return self.spreadsheet_processor.process(file_path, document_id)

        raise ValueError(f"Unsupported document type: {document_type}")
