from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic_settings import BaseSettings
from typing import Optional
import logging
import os
from pathlib import Path
from datetime import datetime

from app.models.schemas import (
    VideoUploadResponse,
    VideoProcessingStatus,
    ChatRequest,
    ChatResponse,
    VideoInfo,
    TimestampReference,
    ErrorResponse
)
from app.services.video_processor import VideoProcessor
from app.services.rag_engine import RAGEngine
from app.services.gemini_client import GeminiClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Settings
class Settings(BaseSettings):
    gemini_api_key: str
    gemini_model: str = "gemini-1.5-pro"
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "video_transcripts"
    max_video_size_mb: int = 500
    upload_dir: str = "./uploads"
    temp_dir: str = "./temp"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    whisper_model: str = "base"

    class Config:
        env_file = ".env"


# Initialize app
app = FastAPI(
    title="Video RAG API",
    description="API for video-based Retrieval-Augmented Generation",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load settings
try:
    settings = Settings()
except Exception as e:
    logger.error(f"Failed to load settings: {e}")
    logger.info("Make sure to create a .env file with required variables")
    raise

# Initialize services
try:
    video_processor = VideoProcessor(
        upload_dir=settings.upload_dir,
        temp_dir=settings.temp_dir,
        whisper_model=settings.whisper_model
    )
    rag_engine = RAGEngine(
        qdrant_host=settings.qdrant_host,
        qdrant_port=settings.qdrant_port,
        collection_name=settings.qdrant_collection,
        gemini_api_key=settings.gemini_api_key,
        embedding_model=settings.embedding_model
    )
    gemini_client = GeminiClient(
        api_key=settings.gemini_api_key,
        model_name=settings.gemini_model
    )
    logger.info("All services initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize services: {e}")
    raise

# Store video metadata
video_metadata = {}


# Background task for processing video
async def process_video_task(video_id: str, video_path: str, filename: str):
    """Background task to process video."""
    try:
        logger.info(f"Starting background processing for video {video_id}")

        # Process video (extract audio, transcribe)
        segments, duration = video_processor.process_video(video_path, video_id)

        # Index segments in Qdrant
        rag_engine.index_video_segments(video_id, segments)

        # Update metadata
        video_metadata[video_id] = {
            "filename": filename,
            "duration": duration,
            "upload_date": datetime.now(),
            "status": "completed",
            "total_segments": len(segments),
            "video_path": video_path
        }

        logger.info(f"Video {video_id} processed successfully")

    except Exception as e:
        logger.error(f"Failed to process video {video_id}: {e}")
        video_metadata[video_id] = {
            "filename": filename,
            "status": "failed",
            "error": str(e)
        }


# Routes
@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "online",
        "service": "Video RAG API",
        "version": "1.0.0"
    }


@app.post("/api/upload", response_model=VideoUploadResponse)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """Upload a video file for processing."""
    try:
        # Validate file type
        allowed_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}
        file_extension = Path(file.filename).suffix.lower()

        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
            )

        # Read file content
        content = await file.read()
        file_size_mb = len(content) / (1024 * 1024)

        if file_size_mb > settings.max_video_size_mb:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {settings.max_video_size_mb}MB"
            )

        # Save video
        video_id, video_path = video_processor.save_video(content, file.filename)

        # Initialize metadata
        video_metadata[video_id] = {
            "filename": file.filename,
            "status": "processing",
            "upload_date": datetime.now()
        }

        # Start background processing
        background_tasks.add_task(process_video_task, video_id, video_path, file.filename)

        return VideoUploadResponse(
            video_id=video_id,
            filename=file.filename,
            status="processing",
            message="Video uploaded successfully. Processing started."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/api/status/{video_id}", response_model=VideoProcessingStatus)
async def get_processing_status(video_id: str):
    """Get processing status for a video."""
    # Check processor status first
    status = video_processor.get_status(video_id)

    if status:
        return VideoProcessingStatus(
            video_id=video_id,
            status=status.get('status', 'unknown'),
            progress=status.get('progress', 0),
            message=status.get('error'),
            total_segments=status.get('total_segments')
        )

    # Check metadata
    if video_id in video_metadata:
        meta = video_metadata[video_id]
        return VideoProcessingStatus(
            video_id=video_id,
            status=meta.get('status', 'unknown'),
            progress=100 if meta.get('status') == 'completed' else 0,
            message=meta.get('error'),
            total_segments=meta.get('total_segments')
        )

    raise HTTPException(status_code=404, detail="Video not found")


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat with the video content."""
    try:
        # Check if video exists and is processed
        if request.video_id not in video_metadata:
            raise HTTPException(status_code=404, detail="Video not found")

        meta = video_metadata[request.video_id]
        if meta['status'] != 'completed':
            raise HTTPException(
                status_code=400,
                detail=f"Video is not ready. Status: {meta['status']}"
            )

        # Search for relevant segments
        relevant_segments = rag_engine.search_segments(
            video_id=request.video_id,
            query=request.message,
            top_k=5
        )

        if not relevant_segments:
            return ChatResponse(
                response="I couldn't find relevant information in the video to answer your question.",
                timestamps=[],
                sources_used=0
            )

        # Generate response using Gemini
        conversation_history = [
            {"role": msg.role, "content": msg.content}
            for msg in request.conversation_history
        ]

        response_text = gemini_client.generate_response(
            query=request.message,
            context_segments=relevant_segments,
            conversation_history=conversation_history
        )

        # Extract timestamp references
        timestamps = [
            TimestampReference(
                start_time=seg['start_time'],
                end_time=seg['end_time'],
                text=seg['text'][:100] + "..." if len(seg['text']) > 100 else seg['text'],
                relevance_score=seg['score']
            )
            for seg in relevant_segments[:3]
        ]

        return ChatResponse(
            response=response_text,
            timestamps=timestamps,
            sources_used=len(relevant_segments)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat failed: {e}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@app.get("/api/video/{video_id}")
async def get_video(video_id: str):
    """Serve video file."""
    if video_id not in video_metadata:
        raise HTTPException(status_code=404, detail="Video not found")

    video_path = video_metadata[video_id].get('video_path')
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found")

    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=video_metadata[video_id]['filename']
    )


@app.get("/api/videos", response_model=list[VideoInfo])
async def list_videos():
    """List all uploaded videos."""
    videos = []
    for video_id, meta in video_metadata.items():
        videos.append(
            VideoInfo(
                video_id=video_id,
                filename=meta['filename'],
                duration=meta.get('duration'),
                upload_date=meta['upload_date'],
                status=meta['status'],
                total_segments=meta.get('total_segments')
            )
        )
    return videos


@app.delete("/api/video/{video_id}")
async def delete_video(video_id: str):
    """Delete a video and its data."""
    if video_id not in video_metadata:
        raise HTTPException(status_code=404, detail="Video not found")

    try:
        # Delete from Qdrant
        rag_engine.delete_video_segments(video_id)

        # Delete video files
        video_processor.cleanup_video(video_id)

        # Remove metadata
        del video_metadata[video_id]

        return {"message": "Video deleted successfully"}

    except Exception as e:
        logger.error(f"Failed to delete video: {e}")
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
