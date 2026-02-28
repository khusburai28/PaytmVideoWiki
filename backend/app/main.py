from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic_settings import BaseSettings
from typing import Optional
import logging
import os
import ffmpeg
from pathlib import Path
from datetime import datetime
from qdrant_client.models import Filter, FieldCondition, MatchValue

from app.models.schemas import (
    VideoUploadRequest,
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
from app.services.report_generator import ReportGenerator
from app.services.auth_service import AuthService
from app.models.auth_schemas import (
    UserCreate, UserLogin, UserResponse, TokenResponse,
    TeamCreate, TeamResponse, AddTeamMemberRequest, AssignUserToTeamRequest,
    TeamMemberResponse, Role
)
from app.middleware.auth import (
    get_current_user, get_current_active_user,
    require_admin, require_team_lead_or_admin, check_video_permission
)

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

# Store video metadata
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

        # Index segments in Qdrant with video duration for derived chunks
        rag_engine.index_video_segments(video_id, segments, duration)

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


# ============= Authentication Endpoints =============

@app.post("/api/auth/register", response_model=TokenResponse)
async def register(user_data: UserCreate):
    """Register a new user."""
    try:
        # Create user
        user_id = auth_service.create_user(
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name,
            role=user_data.role.value,
            team_id=user_data.team_id
        )

        # Get user details
        user = auth_service.get_user_by_id(user_id)

        # Get team name if user has team
        team_name = None
        if user.get('team_id'):
            team = auth_service.get_team_by_id(user['team_id'])
            if team:
                team_name = team.get('team_name')

        # Create access token
        access_token = auth_service.create_access_token(
            user_id=user['user_id'],
            email=user['email'],
            role=user['role']
        )

        user_response = UserResponse(
            user_id=user['user_id'],
            email=user['email'],
            full_name=user['full_name'],
            role=Role(user['role']),
            team_id=user.get('team_id'),
            team_name=team_name,
            created_at=datetime.fromisoformat(user['created_at']),
            is_active=user.get('is_active', True)
        )

        return TokenResponse(access_token=access_token, user=user_response)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    """Login user."""
    try:
        # Authenticate user
        user = auth_service.authenticate_user(credentials.email, credentials.password)

        if not user:
            raise HTTPException(
                status_code=401,
                detail="Incorrect email or password"
            )

        # Get team name if user has team
        team_name = None
        if user.get('team_id'):
            team = auth_service.get_team_by_id(user['team_id'])
            if team:
                team_name = team.get('team_name')

        # Create access token
        access_token = auth_service.create_access_token(
            user_id=user['user_id'],
            email=user['email'],
            role=user['role']
        )

        user_response = UserResponse(
            user_id=user['user_id'],
            email=user['email'],
            full_name=user['full_name'],
            role=Role(user['role']),
            team_id=user.get('team_id'),
            team_name=team_name,
            created_at=datetime.fromisoformat(user['created_at']),
            is_active=user.get('is_active', True)
        )

        return TokenResponse(access_token=access_token, user=user_response)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(status_code=500, detail="Login failed")


@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_active_user)):
    """Get current user information."""
    try:
        # Get team name if user has team
        team_name = None
        if current_user.get('team_id'):
            team = auth_service.get_team_by_id(current_user['team_id'])
            if team:
                team_name = team.get('team_name')

        return UserResponse(
            user_id=current_user['user_id'],
            email=current_user['email'],
            full_name=current_user['full_name'],
            role=Role(current_user['role']),
            team_id=current_user.get('team_id'),
            team_name=team_name,
            created_at=datetime.fromisoformat(current_user['created_at']),
            is_active=current_user.get('is_active', True)
        )
    except Exception as e:
        logger.error(f"Failed to get user info: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user info")


# ============= Team Management Endpoints =============

@app.post("/api/teams", response_model=TeamResponse)
async def create_team(
    team_data: TeamCreate,
    current_user: dict = Depends(require_admin)
):
    """Create a new team (Admin only)."""
    try:
        team_id = auth_service.create_team(
            team_name=team_data.team_name,
            description=team_data.description,
            created_by=current_user['user_id']
        )

        team = auth_service.get_team_by_id(team_id)
        members = auth_service.get_team_members(team_id)

        return TeamResponse(
            team_id=team['team_id'],
            team_name=team['team_name'],
            description=team.get('description'),
            created_by=team['created_by'],
            created_at=datetime.fromisoformat(team['created_at']),
            member_count=len(members)
        )

    except Exception as e:
        logger.error(f"Failed to create team: {e}")
        raise HTTPException(status_code=500, detail="Failed to create team")


@app.post("/api/teams/{team_id}/members", response_model=UserResponse)
async def add_team_member(
    team_id: str,
    member_data: AddTeamMemberRequest,
    current_user: dict = Depends(require_team_lead_or_admin)
):
    """Add a member to team (Team Lead or Admin)."""
    try:
        # Verify team exists
        team = auth_service.get_team_by_id(team_id)
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        # If team lead, verify they belong to this team
        if current_user['role'] == 'team_lead':
            if current_user.get('team_id') != team_id:
                raise HTTPException(
                    status_code=403,
                    detail="Team leads can only add members to their own team"
                )

        # Create user and add to team
        user_id = auth_service.create_user(
            email=member_data.email,
            password=member_data.password,
            full_name=member_data.full_name,
            role=member_data.role.value,
            team_id=team_id
        )

        user = auth_service.get_user_by_id(user_id)

        return UserResponse(
            user_id=user['user_id'],
            email=user['email'],
            full_name=user['full_name'],
            role=Role(user['role']),
            team_id=user.get('team_id'),
            team_name=team['team_name'],
            created_at=datetime.fromisoformat(user['created_at']),
            is_active=user.get('is_active', True)
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add team member: {e}")
        raise HTTPException(status_code=500, detail="Failed to add team member")


@app.get("/api/teams")
async def get_all_teams(current_user: dict = Depends(get_current_active_user)):
    """Get all teams with their members."""
    try:
        teams = auth_service.get_all_teams()

        # Format teams with members
        result = []
        for team in teams:
            members = auth_service.get_team_members(team['team_id'])
            result.append({
                **team,
                'members': members
            })

        return result
    except Exception as e:
        logger.error(f"Failed to get teams: {e}")
        raise HTTPException(status_code=500, detail="Failed to get teams")


@app.get("/api/users")
async def get_all_users(current_user: dict = Depends(require_admin)):
    """Get all users (Admin only)."""
    try:
        users = auth_service.get_all_users()
        return users
    except Exception as e:
        logger.error(f"Failed to get users: {e}")
        raise HTTPException(status_code=500, detail="Failed to get users")


@app.get("/api/teams/{team_id}/members", response_model=list[TeamMemberResponse])
async def get_team_members(
    team_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Get team members."""
    try:
        # Verify team exists
        team = auth_service.get_team_by_id(team_id)
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        # Non-admin users can only view their own team
        if current_user['role'] != 'admin':
            if current_user.get('team_id') != team_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view members of your own team"
                )

        members = auth_service.get_team_members(team_id)

        return [
            TeamMemberResponse(
                user_id=member['user_id'],
                email=member['email'],
                full_name=member['full_name'],
                role=Role(member['role']),
                joined_at=datetime.fromisoformat(member['created_at'])
            )
            for member in members
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get team members: {e}")
        raise HTTPException(status_code=500, detail="Failed to get team members")


@app.post("/api/upload", response_model=VideoUploadResponse)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form(...),
    current_user: dict = Depends(get_current_active_user)
):
    """Upload a video file for processing (Authenticated users only)."""
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
            "name": name,
            "description": description,
            "status": "processing",
            "upload_date": datetime.now(),
            "author_id": current_user['user_id'],
            "team_id": current_user.get('team_id')
        }

        # Start background processing
        background_tasks.add_task(
            process_video_task,
            video_id,
            video_path,
            file.filename,
            name,
            description,
            current_user['user_id'],
            current_user.get('team_id')
        )

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
    # Check processor status first (for videos currently being processed)
    status = video_processor.get_status(video_id)

    if status:
        return VideoProcessingStatus(
            video_id=video_id,
            status=status.get('status', 'unknown'),
            progress=status.get('progress', 0),
            message=status.get('error'),
            total_segments=status.get('total_segments')
        )

    # Check if video is indexed in Qdrant (completed videos)
    segment_count = rag_engine.get_video_segment_count(video_id)
    if segment_count > 0:
        return VideoProcessingStatus(
            video_id=video_id,
            status='completed',
            progress=100,
            message=None,
            total_segments=segment_count
        )

    raise HTTPException(status_code=404, detail="Video not found")


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat with the video content."""
    try:
        # Check if video exists in Qdrant
        segment_count = rag_engine.get_video_segment_count(request.video_id)
        if segment_count == 0:
            raise HTTPException(status_code=404, detail="Video not found or not indexed")

        # Search for relevant segments
        logger.info(f"User query: '{request.message}'")
        relevant_segments = rag_engine.search_segments(
            video_id=request.video_id,
            query=request.message,
            top_k=5
        )

        if not relevant_segments:
            logger.info("No relevant segments found for query")
            return ChatResponse(
                response="I couldn't find relevant information in the video to answer your question.",
                timestamps=[],
                sources_used=0
            )

        # Log retrieved segments with scores
        logger.info(f"Retrieved {len(relevant_segments)} segments for query:")
        for idx, seg in enumerate(relevant_segments, 1):
            timestamp = f"{int(seg['start_time']//60)}:{int(seg['start_time']%60):02d}"
            text_preview = seg['text'][:80] + "..." if len(seg['text']) > 80 else seg['text']
            logger.info(f"  {idx}. [Score: {seg['score']:.4f}] [{timestamp}] {text_preview}")

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
async def get_video(video_id: str, request: Request):
    """Serve video file with range request support."""
    # Find video file by video_id
    upload_dir = Path(settings.upload_dir)
    video_file = None

    for ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
        potential_file = upload_dir / f"{video_id}{ext}"
        if potential_file.exists():
            video_file = potential_file
            break

    if not video_file:
        raise HTTPException(status_code=404, detail="Video file not found")

    # Get file size
    file_size = os.path.getsize(video_file)

    # Get range header
    range_header = request.headers.get('Range')

    if not range_header:
        # No range requested, return full file
        return FileResponse(
            str(video_file),
            media_type="video/mp4",
            filename=video_file.name
        )

    # Parse range header
    byte_range = range_header.replace('bytes=', '').split('-')
    start = int(byte_range[0]) if byte_range[0] else 0
    end = int(byte_range[1]) if len(byte_range) > 1 and byte_range[1] else file_size - 1

    # Ensure valid range
    if start >= file_size or end >= file_size:
        raise HTTPException(status_code=416, detail="Range not satisfiable")

    chunk_size = end - start + 1

    # Read and stream the requested byte range
    def iterfile():
        with open(video_file, 'rb') as f:
            f.seek(start)
            remaining = chunk_size
            while remaining > 0:
                chunk = f.read(min(8192, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    headers = {
        'Content-Range': f'bytes {start}-{end}/{file_size}',
        'Accept-Ranges': 'bytes',
        'Content-Length': str(chunk_size),
        'Content-Type': 'video/mp4',
    }

    return StreamingResponse(
        iterfile(),
        status_code=206,
        headers=headers
    )


@app.get("/api/videos", response_model=list[VideoInfo])
async def list_videos():
    """List all uploaded videos by querying Qdrant metadata collection."""
    try:
        # Get all video metadata from Qdrant
        all_metadata = rag_engine.list_all_video_metadata()

        videos = []
        for metadata in all_metadata:
            videos.append(
                VideoInfo(
                    video_id=metadata.get('video_id'),
                    name=metadata.get('name', 'Untitled'),
                    description=metadata.get('description', ''),
                    filename=metadata.get('filename'),
                    duration=metadata.get('duration'),
                    upload_date=datetime.fromisoformat(metadata.get('upload_date')),
                    status='completed',
                    total_segments=metadata.get('total_segments', 0)
                )
            )

        return videos
    except Exception as e:
        logger.error(f"Failed to list videos: {e}")
        return []


@app.post("/api/video/{video_id}/report")
async def generate_report(video_id: str):
    """Generate a comprehensive PDF report for the video."""
    try:
        # Get video metadata
        metadata = rag_engine.get_video_metadata(video_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Video not found")

        # Get all segments for the video
        logger.info(f"Retrieving all segments for video {video_id}")
        all_segments = []
        offset = None

        while True:
            records, offset = rag_engine.qdrant_client.scroll(
                collection_name=rag_engine.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="video_id",
                            match=MatchValue(value=video_id)
                        ),
                        FieldCondition(
                            key="chunk_type",
                            match=MatchValue(value="regular")
                        )
                    ]
                ),
                limit=100,
                with_payload=True,
                with_vectors=False
            )

            for record in records:
                all_segments.append({
                    'text': record.payload['text'],
                    'start_time': record.payload['start_time'],
                    'end_time': record.payload['end_time'],
                    'segment_index': record.payload.get('segment_index', 0)
                })

            if offset is None:
                break

        # Sort segments by time
        all_segments.sort(key=lambda x: x['start_time'])
        logger.info(f"Retrieved {len(all_segments)} segments")

        # Generate report content
        report_markdown = report_generator.generate_report_content(
            video_name=metadata.get('name', 'Untitled Video'),
            description=metadata.get('description', ''),
            duration=metadata.get('duration', 0),
            segments=all_segments
        )

        # Convert to PDF
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            pdf_path = tmp_file.name

        report_generator.markdown_to_pdf(report_markdown, pdf_path)

        # Return PDF file
        return FileResponse(
            pdf_path,
            media_type='application/pdf',
            filename=f"{metadata.get('name', 'video')}_report.pdf",
            background=BackgroundTasks().add_task(lambda: os.remove(pdf_path) if os.path.exists(pdf_path) else None)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate report: {e}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


@app.delete("/api/video/{video_id}")
async def delete_video(video_id: str, current_user: dict = Depends(get_current_active_user)):
    """Delete a video and its data (Author, Team Lead, or Admin only)."""
    # Check if video exists in Qdrant
    segment_count = rag_engine.get_video_segment_count(video_id)
    if segment_count == 0:
        raise HTTPException(status_code=404, detail="Video not found")

    try:
        # Get video metadata to check permissions
        metadata = rag_engine.get_video_metadata(video_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Video metadata not found")

        # Check if user has permission to delete
        if not check_video_permission(metadata, current_user):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to delete this video. Only the author, team lead, or admin can delete."
            )

        # Delete from Qdrant (segments and metadata)
        rag_engine.delete_video_segments(video_id)
        rag_engine.delete_video_metadata(video_id)

        # Delete video files
        video_processor.cleanup_video(video_id)

        # Remove from in-memory metadata if exists (for currently processing videos)
        if video_id in video_metadata:
            del video_metadata[video_id]

        return {"message": "Video deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete video: {e}")
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
