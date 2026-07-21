from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime

DocumentType = Literal["video", "pdf", "image", "spreadsheet"]


class DocumentUploadRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Document title/name")
    description: str = Field(..., min_length=1, max_length=1000, description="Short description of the document")


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    document_type: DocumentType
    status: str
    message: str


class TranscriptSegment(BaseModel):
    text: str
    start_time: float
    end_time: float
    confidence: Optional[float] = None


class DocumentProcessingStatus(BaseModel):
    document_id: str
    status: str  # "processing", "completed", "failed"
    progress: int  # 0-100
    message: Optional[str] = None
    total_segments: Optional[int] = None


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[datetime] = None


class ChatRequest(BaseModel):
    document_id: Optional[str] = None  # None = search across the user's full team corpus
    message: str
    conversation_history: List[ChatMessage] = Field(default_factory=list)


class SourceReference(BaseModel):
    document_id: str
    document_name: str
    document_type: DocumentType
    locator: str  # e.g. "12:34", "Page 4", "Sheet: WorkOrders, Rows 12-21", "Full image"
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    page_number: Optional[int] = None
    sheet_name: Optional[str] = None
    row_range: Optional[str] = None
    text: str
    relevance_score: float


class ChatResponse(BaseModel):
    response: str
    sources: List[SourceReference]
    sources_used: int


class DocumentInfo(BaseModel):
    document_id: str
    document_type: DocumentType
    name: str
    description: str
    filename: str
    duration: Optional[float] = None
    upload_date: datetime
    status: str
    total_segments: Optional[int] = None
    author_name: Optional[str] = None


class ReportGenerationRequest(BaseModel):
    additional_instructions: Optional[str] = None


class DiagramGenerationRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User query for diagram generation")


class DiagramGenerationResponse(BaseModel):
    diagram: str = Field(..., description="Mermaid diagram syntax")


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
