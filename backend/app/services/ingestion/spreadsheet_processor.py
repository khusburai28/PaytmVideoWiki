import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

ROWS_PER_CHUNK = 10


class SpreadsheetProcessor:
    """Parses XLSX/XLS/CSV files into a per-sheet summary chunk plus grouped-row chunks,
    mirroring the video pipeline's "merge into meaningful chunks" philosophy."""

    def __init__(self, gemini_client, status_store: Optional[Dict] = None):
        self.gemini_client = gemini_client
        self.status_store = status_store if status_store is not None else {}

    def _set_status(self, document_id: str, status: str, progress: int, message: str):
        self.status_store[document_id] = {"status": status, "progress": progress, "message": message}

    def process(self, file_path: str, document_id: str) -> Tuple[List[Dict], Dict]:
        self._set_status(document_id, "parsing_spreadsheet", 20, "Parsing spreadsheet...")

        path = Path(file_path)
        if path.suffix.lower() == ".csv":
            sheets = {"Sheet1": pd.read_csv(file_path, dtype=str).fillna("")}
        else:
            raw_sheets = pd.read_excel(file_path, sheet_name=None, dtype=str)
            sheets = {name: df.fillna("") for name, df in raw_sheets.items()}

        self._set_status(document_id, "processing_segments", 60, "Summarizing sheets and grouping rows...")

        segments = []
        sheet_names = list(sheets.keys())

        for sheet_name, df in sheets.items():
            columns = [str(c) for c in df.columns]

            segments.append({
                "text": self._describe_sheet(sheet_name, columns, len(df)),
                "sheet_name": sheet_name,
                "confidence": 1.0
            })

            for start in range(0, len(df), ROWS_PER_CHUNK):
                chunk_df = df.iloc[start:start + ROWS_PER_CHUNK]
                row_texts = []
                for _, row in chunk_df.iterrows():
                    row_text = "; ".join(
                        f"{col}: {row[col]}" for col in columns if str(row[col]).strip()
                    )
                    if row_text:
                        row_texts.append(row_text)
                end = min(start + ROWS_PER_CHUNK, len(df))
                if row_texts:
                    segments.append({
                        "text": f"Rows {start + 1}-{end} of sheet '{sheet_name}':\n" + "\n".join(row_texts),
                        "sheet_name": sheet_name,
                        "row_range": f"{start + 1}-{end}",
                        "confidence": 1.0
                    })

        if not segments:
            segments.append({"text": "(Spreadsheet contained no rows.)", "confidence": 0.0})

        self._set_status(document_id, "completed", 100, "Spreadsheet processing completed successfully!")
        return segments, {"duration": None, "sheet_names": sheet_names}

    def _describe_sheet(self, sheet_name: str, columns: List[str], row_count: int) -> str:
        try:
            prompt = (
                f"A spreadsheet sheet named '{sheet_name}' has {row_count} rows and columns: "
                f"{', '.join(columns)}. In 1-2 sentences, describe what this sheet likely tracks "
                f"in an industrial/maintenance context."
            )
            description = self.gemini_client.generate_content(prompt)
            return f"SHEET SUMMARY ({sheet_name}): {description.strip()} Columns: {', '.join(columns)}. Row count: {row_count}."
        except Exception as e:
            logger.warning(f"Failed to summarize sheet {sheet_name}: {e}")
            return f"SHEET SUMMARY ({sheet_name}): Columns: {', '.join(columns)}. Row count: {row_count}."
