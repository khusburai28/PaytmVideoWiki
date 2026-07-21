from pathlib import Path
from typing import Dict, List, Tuple, Optional
import mimetypes
import logging

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Indexes a standalone image (equipment nameplate, P&ID snapshot, scanned form, photo)
    as a single chunk describing/transcribing its content via Gemini vision."""

    def __init__(self, gemini_client, status_store: Optional[Dict] = None):
        self.gemini_client = gemini_client
        self.status_store = status_store if status_store is not None else {}

    def _set_status(self, document_id: str, status: str, progress: int, message: str):
        self.status_store[document_id] = {"status": status, "progress": progress, "message": message}

    def process(self, file_path: str, document_id: str) -> Tuple[List[Dict], Dict]:
        self._set_status(document_id, "analyzing_image", 40, "Analyzing image with Gemini vision...")

        with open(file_path, "rb") as f:
            image_bytes = f.read()

        mime_type = mimetypes.guess_type(Path(file_path).name)[0] or "image/png"

        try:
            description = self.gemini_client.describe_image(
                image_bytes=image_bytes,
                mime_type=mime_type,
                instruction=(
                    "This is an industrial asset image - it could be an equipment nameplate, a "
                    "P&ID-style diagram, a photo of equipment, or a scanned form. Transcribe all "
                    "readable text exactly (asset tags, model/serial numbers, ratings, labels), then "
                    "briefly describe what the image shows."
                )
            )
        except Exception as e:
            logger.error(f"Image analysis failed for {document_id}: {e}")
            description = "(Image could not be analyzed.)"

        self._set_status(document_id, "completed", 100, "Image processing completed successfully!")

        segments = [{"text": description, "confidence": 1.0}]
        return segments, {"duration": None}
