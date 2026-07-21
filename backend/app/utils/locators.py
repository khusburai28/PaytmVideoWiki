from typing import Dict


def format_timestamp(seconds: float) -> str:
    """Format seconds to MM:SS or HH:MM:SS."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_locator(segment: Dict) -> str:
    """Build a human-readable source locator from a chunk payload, independent of document type."""
    document_type = segment.get("document_type", "video")

    if document_type == "video" and segment.get("start_time") is not None:
        return format_timestamp(segment["start_time"])

    if segment.get("page_number") is not None:
        return f"Page {segment['page_number']}"

    if segment.get("sheet_name"):
        row_range = segment.get("row_range")
        if row_range:
            return f"Sheet: {segment['sheet_name']}, Rows {row_range}"
        return f"Sheet: {segment['sheet_name']}"

    if document_type == "image":
        return "Full image"

    return "Document"
