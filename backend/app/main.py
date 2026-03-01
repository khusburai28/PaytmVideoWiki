from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings
from typing import Optional
from datetime import datetime
import logging

from app.services.video_processor import VideoProcessor
from app.services.rag_engine import RAGEngine
from app.services.gemini_client import GeminiClient
from app.services.report_generator import ReportGenerator
from app.services.auth_service import AuthService

# Import routers
from app.routers import auth, teams, videos, users

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Settings
class Settings(BaseSettings):
    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash"
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "video_transcripts"
    max_video_size_mb: int = 500
    upload_dir: str = "./uploads"
    temp_dir: str = "./temp"
    embedding_model: str = "gemini-embedding-001"
    whisper_model: str = "base"
    jwt_secret_key: str = "your-secret-key-change-in-production-min-32-chars"

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
    report_generator = ReportGenerator(gemini_client=gemini_client)
    auth_service = AuthService(
        qdrant_client=rag_engine.qdrant_client,
        secret_key=settings.jwt_secret_key
    )
    logger.info("All services initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize services: {e}")
    raise

# Store video metadata (in-memory cache for processing status)
video_metadata = {}


# Background task for processing video
async def process_video_task(
    video_id: str,
    video_path: str,
    filename: str,
    name: str,
    description: str,
    author_id: str,
    team_id: Optional[str] = None
):
    """Background task to process video."""
    try:
        logger.info(f"Starting background processing for video {video_id}")

        # Process video (extract audio, transcribe)
        segments, duration = video_processor.process_video(video_path, video_id)

        # Update status for indexing
        video_processor.processing_status[video_id] = {
            "status": "indexing",
            "progress": 85,
            "message": "Indexing transcript for AI search..."
        }

        # Index segments in Qdrant with video duration for derived chunks
        rag_engine.index_video_segments(video_id, segments, duration)

        # Update status for finalizing
        video_processor.processing_status[video_id] = {
            "status": "finalizing",
            "progress": 95,
            "message": "Finalizing and saving metadata..."
        }

        # Save video metadata to Qdrant
        rag_engine.save_video_metadata(
            video_id=video_id,
            name=name,
            description=description,
            duration=duration,
            filename=filename,
            total_segments=len(segments),
            author_id=author_id,
            team_id=team_id
        )

        # Update in-memory metadata for status tracking
        video_metadata[video_id] = {
            "filename": filename,
            "name": name,
            "description": description,
            "duration": duration,
            "upload_date": datetime.now(),
            "status": "completed",
            "total_segments": len(segments),
            "video_path": video_path,
            "author_id": author_id,
            "team_id": team_id
        }

        # Final status update
        video_processor.processing_status[video_id] = {
            "status": "completed",
            "progress": 100,
            "message": "Video ready for AI-powered search!",
            "total_segments": len(segments)
        }

        logger.info(f"Video {video_id} processed successfully")

    except Exception as e:
        logger.error(f"Failed to process video {video_id}: {e}")
        video_processor.processing_status[video_id] = {
            "status": "failed",
            "progress": 0,
            "error": str(e),
            "message": f"Processing failed: {str(e)}"
        }
        if video_id in video_metadata:
            video_metadata[video_id]["status"] = "failed"
            video_metadata[video_id]["error"] = str(e)


# Include routers
app.include_router(auth.router)
app.include_router(teams.router)
app.include_router(videos.router)
app.include_router(users.router)


@app.get("/")
async def root():
    """Root endpoint - API health check."""
    return {
        "message": "Video RAG API is running",
        "version": "1.0.0",
        "status": "healthy"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "services": {
            "video_processor": "ok",
            "rag_engine": "ok",
            "gemini_client": "ok",
            "auth_service": "ok"
        }
    }
