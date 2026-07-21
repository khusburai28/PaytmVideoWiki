from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings
from typing import Optional
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
import os

from app.services.video_processor import VideoProcessor
from app.services.rag_engine import RAGEngine
from app.services.gemini_client import GeminiClient
from app.services.report_generator import ReportGenerator
from app.services.auth_service import AuthService
from app.services.knowledge_graph import KnowledgeGraphService
from app.services.ingestion.dispatcher import DocumentDispatcher

# Import routers
from app.routers import auth, teams, videos, users, graph

# Configure logging with file rotation
os.makedirs("logs", exist_ok=True)

# File handler with rotation (10MB per file, keep 5 backups)
file_handler = RotatingFileHandler(
    'logs/app.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
file_handler.setLevel(logging.INFO)

# Console handler for Docker logs
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)
logger = logging.getLogger(__name__)


# Settings
class Settings(BaseSettings):
    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash"
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "document_chunks"
    qdrant_metadata_collection: str = "document_metadata"
    max_video_size_mb: int = 500
    upload_dir: str = "./uploads"
    temp_dir: str = "./temp"
    data_dir: str = "./data"
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

# Request/Response logging middleware
from app.middleware.logging_middleware import RequestResponseLoggingMiddleware
app.add_middleware(RequestResponseLoggingMiddleware)

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
        metadata_collection_name=settings.qdrant_metadata_collection,
        gemini_api_key=settings.gemini_api_key,
        embedding_model=settings.embedding_model,
        gemini_model=settings.gemini_model
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
    knowledge_graph_service = KnowledgeGraphService(
        gemini_client=gemini_client,
        storage_path=f"{settings.data_dir}/knowledge_graph.json"
    )
    document_dispatcher = DocumentDispatcher(
        video_processor=video_processor,
        gemini_client=gemini_client
    )
    logger.info("All services initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize services: {e}")
    raise

# Store document metadata (in-memory cache for processing status, keyed by document_id)
document_metadata = {}


# Background task for processing an uploaded document of any supported type
async def process_document_task(
    document_id: str,
    document_type: str,
    file_path: str,
    filename: str,
    name: str,
    description: str,
    author_id: str,
    team_id: Optional[str] = None
):
    """Background task to ingest a document: dispatch to the type-specific processor,
    index the resulting chunks, extract knowledge-graph entities, and save metadata."""
    try:
        logger.info(f"Starting background processing for {document_type} document {document_id}")

        # Dispatch to the right processor (video/pdf/image/spreadsheet)
        segments, extra_metadata = document_dispatcher.process(document_type, file_path, document_id)
        duration = extra_metadata.pop("duration", None)

        # Update status for indexing
        video_processor.processing_status[document_id] = {
            "status": "indexing",
            "progress": 85,
            "message": "Indexing content for AI search..."
        }

        # Index chunks in Qdrant
        indexed_segments = rag_engine.index_document_chunks(
            document_id=document_id,
            document_type=document_type,
            segments=segments,
            team_id=team_id,
            author_id=author_id
        )

        # Update status for graph extraction
        video_processor.processing_status[document_id] = {
            "status": "extracting_entities",
            "progress": 92,
            "message": "Extracting knowledge graph entities..."
        }

        # Extract knowledge-graph entities/relationships (best-effort - never blocks ingestion)
        try:
            full_text = " ".join(seg["text"] for seg in segments)
            knowledge_graph_service.extract_and_merge(
                document_id=document_id,
                document_name=name,
                document_type=document_type,
                full_text=full_text
            )
        except Exception as e:
            logger.warning(f"Knowledge graph extraction failed for {document_id}: {e}")

        # Update status for finalizing
        video_processor.processing_status[document_id] = {
            "status": "finalizing",
            "progress": 95,
            "message": "Finalizing and saving metadata..."
        }

        # Save document metadata to Qdrant
        rag_engine.save_document_metadata(
            document_id=document_id,
            document_type=document_type,
            name=name,
            description=description,
            duration=duration,
            filename=filename,
            total_segments=len(segments),
            author_id=author_id,
            team_id=team_id,
            extra=extra_metadata
        )

        # Update in-memory metadata for status tracking
        document_metadata[document_id] = {
            "filename": filename,
            "document_type": document_type,
            "name": name,
            "description": description,
            "duration": duration,
            "upload_date": datetime.now(),
            "status": "completed",
            "total_segments": len(segments),
            "file_path": file_path,
            "author_id": author_id,
            "team_id": team_id
        }

        # Final status update
        video_processor.processing_status[document_id] = {
            "status": "completed",
            "progress": 100,
            "message": "Document ready for AI-powered search!",
            "total_segments": len(segments)
        }

        logger.info(f"Document {document_id} processed successfully")

    except Exception as e:
        logger.error(f"Failed to process document {document_id}: {e}")
        video_processor.processing_status[document_id] = {
            "status": "failed",
            "progress": 0,
            "error": str(e),
            "message": f"Processing failed: {str(e)}"
        }
        if document_id in document_metadata:
            document_metadata[document_id]["status"] = "failed"
            document_metadata[document_id]["error"] = str(e)


# Include routers
app.include_router(auth.router)
app.include_router(teams.router)
app.include_router(videos.router)
app.include_router(users.router)
app.include_router(graph.router)


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
