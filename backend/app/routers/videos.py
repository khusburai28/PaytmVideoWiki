from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks, Request, Depends
from fastapi.responses import StreamingResponse
from pathlib import Path
from datetime import datetime
from qdrant_client.models import Filter, FieldCondition, MatchValue
from typing import List, Optional
import logging
import json

from app.models.schemas import (
    VideoUploadResponse, VideoProcessingStatus, ChatRequest, ChatResponse,
    VideoInfo, TimestampReference, ReportGenerationRequest,
    DiagramGenerationRequest, DiagramGenerationResponse
)
from app.middleware.auth import get_current_active_user, check_video_permission, require_team_membership, require_team_membership_flexible

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["videos"])


def get_dependencies():
    """Get service dependencies from main app."""
    from app.main import (
        settings, video_processor, rag_engine, gemini_client,
        report_generator, video_metadata, process_video_task, auth_service
    )
    return settings, video_processor, rag_engine, gemini_client, report_generator, video_metadata, process_video_task, auth_service


@router.post("/upload", response_model=VideoUploadResponse)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form(...),
    current_user: dict = Depends(require_team_membership)
):
    """Upload a video file for processing (Team members only)."""
    settings, video_processor, rag_engine, gemini_client, report_generator, video_metadata, process_video_task, auth_service = get_dependencies()

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


@router.get("/status/{video_id}", response_model=VideoProcessingStatus)
async def get_processing_status(video_id: str, current_user: dict = Depends(require_team_membership)):
    """Get processing status for a video."""
    settings, video_processor, rag_engine, gemini_client, report_generator, video_metadata, process_video_task, auth_service = get_dependencies()

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


@router.post("/chat", response_model=ChatResponse)
async def chat_with_video(
    video_id: str = Form(...),
    message: str = Form(...),
    conversation_history: str = Form("[]"),
    files: List[UploadFile] = File(default=[]),
    current_user: dict = Depends(require_team_membership)
):
    """Chat with AI about video content with optional file uploads."""
    settings, video_processor, rag_engine, gemini_client, report_generator, video_metadata, process_video_task, auth_service = get_dependencies()

    try:
        # Parse conversation history
        conv_history = json.loads(conversation_history) if conversation_history else []

        # Process uploaded files if any
        file_contents = []
        if files:
            for file in files:
                content = await file.read()
                file_info = {
                    "filename": file.filename,
                    "content_type": file.content_type,
                    "size": len(content),
                    "content": content
                }
                file_contents.append(file_info)
                logger.info(f"Received file: {file.filename} ({file.content_type}, {len(content)} bytes)")

        # Search for relevant segments from video
        relevant_segments = rag_engine.search_segments(
            video_id=video_id,
            query=message,
            top_k=15
        )

        if not relevant_segments and not file_contents:
            return ChatResponse(
                response="I couldn't find any relevant information in the video for your question.",
                timestamps=[],
                sources_used=0
            )

        # Generate response using Gemini (with files if provided)
        response_text = gemini_client.generate_response_with_files(
            query=message,
            context_segments=relevant_segments,
            conversation_history=conv_history,
            files=file_contents
        )

        # Extract timestamps as references
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

    except Exception as e:
        logger.error(f"Chat failed: {e}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.get("/video/{video_id}")
async def get_video(
    video_id: str,
    request: Request,
    current_user: dict = Depends(require_team_membership_flexible)
):
    """Stream video file with range request support."""
    settings, video_processor, rag_engine, gemini_client, report_generator, video_metadata, process_video_task, auth_service = get_dependencies()

    try:
        video_path = video_processor.upload_dir / f"{video_id}.mp4"

        if not video_path.exists():
            raise HTTPException(status_code=404, detail="Video not found")

        file_size = video_path.stat().st_size
        range_header = request.headers.get('Range')

        if range_header:
            # Handle range request for video seeking
            range_match = range_header.replace('bytes=', '').split('-')
            start = int(range_match[0])
            end = int(range_match[1]) if range_match[1] else file_size - 1

            def iterfile():
                with open(video_path, 'rb') as video_file:
                    video_file.seek(start)
                    remaining = end - start + 1
                    chunk_size = 1024 * 1024  # 1MB chunks
                    while remaining:
                        chunk = video_file.read(min(chunk_size, remaining))
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        yield chunk

            headers = {
                'Content-Range': f'bytes {start}-{end}/{file_size}',
                'Accept-Ranges': 'bytes',
                'Content-Length': str(end - start + 1),
                'Content-Type': 'video/mp4',
            }

            return StreamingResponse(
                iterfile(),
                status_code=206,
                headers=headers,
                media_type='video/mp4'
            )
        else:
            # Return full file
            def iterfile():
                with open(video_path, 'rb') as video_file:
                    while chunk := video_file.read(1024 * 1024):
                        yield chunk

            return StreamingResponse(
                iterfile(),
                media_type='video/mp4',
                headers={'Accept-Ranges': 'bytes'}
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stream video: {e}")
        raise HTTPException(status_code=500, detail="Failed to stream video")


@router.get("/videos", response_model=list[VideoInfo])
async def list_videos(current_user: dict = Depends(require_team_membership)):
    """Get list of all processed videos."""
    settings, video_processor, rag_engine, gemini_client, report_generator, video_metadata, process_video_task, auth_service = get_dependencies()

    try:
        videos = []
        metadata_list = rag_engine.list_all_video_metadata()

        for metadata in metadata_list:
            # Get author name
            author_name = None
            author_id = metadata.get('author_id')
            if author_id:
                try:
                    user = auth_service.get_user_by_id(author_id)
                    if user:
                        author_name = user.get('full_name')
                except Exception as e:
                    logger.warning(f"Failed to fetch author name for user {author_id}: {e}")

            videos.append(VideoInfo(
                video_id=metadata['video_id'],
                filename=metadata.get('filename', ''),
                name=metadata.get('name', metadata.get('filename', '')),
                description=metadata.get('description'),
                upload_date=datetime.fromisoformat(metadata['upload_date']) if 'upload_date' in metadata else datetime.now(),
                total_segments=metadata.get('total_segments', 0),
                duration=metadata.get('duration', 0),
                status='completed',
                author_name=author_name
            ))

        return sorted(videos, key=lambda x: x.upload_date, reverse=True)

    except Exception as e:
        logger.error(f"Failed to list videos: {e}")
        raise HTTPException(status_code=500, detail="Failed to list videos")


@router.post("/video/{video_id}/report")
async def generate_video_report(
    video_id: str,
    request: ReportGenerationRequest = ReportGenerationRequest(),
    current_user: dict = Depends(require_team_membership)
):
    """Generate PDF report for a video with optional additional instructions."""
    settings, video_processor, rag_engine, gemini_client, report_generator, video_metadata, process_video_task, auth_service = get_dependencies()

    try:
        # Get video metadata
        metadata = rag_engine.get_video_metadata(video_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Video not found")

        # Get full transcript
        results = rag_engine.qdrant_client.scroll(
            collection_name=rag_engine.collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="video_id", match=MatchValue(value=video_id)),
                    FieldCondition(key="chunk_type", match=MatchValue(value="regular"))
                ]
            ),
            limit=10000,
            with_payload=True,
            with_vectors=False
        )

        segments = [r.payload for r in results[0]]
        segments.sort(key=lambda x: x['start_time'])

        # Generate report with optional additional instructions
        report_path = await report_generator.generate_report(
            video_id=video_id,
            video_name=metadata.get('name', metadata.get('filename', 'Untitled')),
            video_description=metadata.get('description', ''),
            duration=metadata.get('duration', 0),
            segments=segments,
            additional_instructions=request.additional_instructions
        )

        # Return PDF file
        def iterfile():
            with open(report_path, 'rb') as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk

        return StreamingResponse(
            iterfile(),
            media_type='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{metadata.get("name", "video")}_report.pdf"'
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate report: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@router.post("/video/{video_id}/diagram", response_model=DiagramGenerationResponse)
async def generate_video_diagram(
    video_id: str,
    request: DiagramGenerationRequest,
    current_user: dict = Depends(require_team_membership)
):
    """Generate a Mermaid diagram based on video content and user query."""
    settings, video_processor, rag_engine, gemini_client, report_generator, video_metadata, process_video_task, auth_service = get_dependencies()

    try:
        # Get video metadata
        metadata = rag_engine.get_video_metadata(video_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Video not found")

        # Get full transcript segments (same as report generation)
        results = rag_engine.qdrant_client.scroll(
            collection_name=rag_engine.collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="video_id", match=MatchValue(value=video_id)),
                    FieldCondition(key="chunk_type", match=MatchValue(value="regular"))
                ]
            ),
            limit=10000,
            with_payload=True,
            with_vectors=False
        )

        segments = [r.payload for r in results[0]]
        segments.sort(key=lambda x: x['start_time'])

        # Generate Mermaid diagram using Gemini
        diagram_code = gemini_client.generate_diagram(
            query=request.query,
            segments=segments
        )

        return DiagramGenerationResponse(diagram=diagram_code)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate diagram: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate diagram: {str(e)}")


@router.delete("/video/{video_id}")
async def delete_video(video_id: str, current_user: dict = Depends(get_current_active_user)):
    """Delete a video and its data (Author, Team Lead, or Admin only)."""
    settings, video_processor, rag_engine, gemini_client, report_generator, video_metadata, process_video_task, auth_service = get_dependencies()

    try:
        # Get video metadata to check permissions
        metadata = rag_engine.get_video_metadata(video_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Video not found")

        # Check if user has permission to delete
        if not check_video_permission(metadata, current_user):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to delete this video"
            )

        # Delete video segments from Qdrant
        rag_engine.delete_video_segments(video_id)

        # Delete video metadata from Qdrant
        rag_engine.delete_video_metadata(video_id)

        # Delete video file
        video_path = video_processor.upload_dir / f"{video_id}.mp4"
        if video_path.exists():
            video_path.unlink()

        # Delete from in-memory metadata
        if video_id in video_metadata:
            del video_metadata[video_id]

        logger.info(f"Deleted video {video_id} by user {current_user['user_id']}")

        return {"message": "Video deleted successfully", "video_id": video_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete video: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete video: {str(e)}")
