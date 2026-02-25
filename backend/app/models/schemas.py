from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class VideoUploadRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Video title/name")
    description: str = Field(..., min_length=1, max_length=1000, description="Short description of the video")


class VideoUploadResponse(BaseModel):
    video_id: str
    filename: str
    status: str
    message: str


class TranscriptSegment(BaseModel):
    text: str
    start_time: float
    end_time: float
    confidence: Optional[float] = None


class VideoProcessingStatus(BaseModel):
    video_id: str
    status: str  # "processing", "completed", "failed"
    progress: int  # 0-100
    message: Optional[str] = None
    total_segments: Optional[int] = None


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[datetime] = None


class ChatRequest(BaseModel):
    video_id: str
    message: str
    conversation_history: List[ChatMessage] = Field(default_factory=list)


class TimestampReference(BaseModel):
    start_time: float
    end_time: float
    text: str
    relevance_score: float


class ChatResponse(BaseModel):
    response: str
    timestamps: List[TimestampReference]
    sources_used: int


class VideoInfo(BaseModel):
    video_id: str
    name: str
    description: str
    filename: str
    duration: Optional[float] = None
    upload_date: datetime
    status: str
    total_segments: Optional[int] = None


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
