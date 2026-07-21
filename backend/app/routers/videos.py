from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks, Request, Depends
from fastapi.responses import StreamingResponse
from pathlib import Path
from datetime import datetime
from qdrant_client.models import Filter, FieldCondition, MatchValue
from typing import List, Optional
import logging
import json
import mimetypes
import pandas as pd

from app.models.schemas import (
    DocumentUploadResponse, DocumentProcessingStatus, ChatRequest, ChatResponse,
    DocumentInfo, SourceReference, ReportGenerationRequest,
    DiagramGenerationRequest, DiagramGenerationResponse
)
from app.services.ingestion.dispatcher import detect_document_type, ALL_ALLOWED_EXTENSIONS
from app.utils.locators import format_locator
from app.middleware.auth import get_current_active_user, check_video_permission, require_team_membership, require_team_membership_flexible

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["documents"])


def get_dependencies():
    """Get service dependencies from main app."""
    from app.main import (
        settings, video_processor, rag_engine, gemini_client,
        report_generator, document_metadata, process_document_task, auth_service, knowledge_graph_service
    )
    return (settings, video_processor, rag_engine, gemini_client, report_generator,
            document_metadata, process_document_task, auth_service, knowledge_graph_service)


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form(...),
    current_user: dict = Depends(require_team_membership)
):
    """Upload a document (video, PDF, image, or spreadsheet) for ingestion (team members only)."""
    (settings, video_processor, rag_engine, gemini_client, report_generator,
     document_metadata, process_document_task, auth_service, knowledge_graph_service) = get_dependencies()

    try:
        document_type = detect_document_type(file.filename)
        if not document_type:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Allowed: {', '.join(sorted(ALL_ALLOWED_EXTENSIONS))}"
            )

        # Read file content
        content = await file.read()
        file_size_mb = len(content) / (1024 * 1024)

        if file_size_mb > settings.max_video_size_mb:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {settings.max_video_size_mb}MB"
            )

        # Save file (generic - just writes bytes under the document's id + original extension)
        document_id, file_path = video_processor.save_video(content, file.filename)

        # Initialize metadata
        document_metadata[document_id] = {
            "filename": file.filename,
            "document_type": document_type,
            "name": name,
            "description": description,
            "status": "processing",
            "upload_date": datetime.now(),
            "author_id": current_user['user_id'],
            "team_id": current_user.get('team_id')
        }

        # Start background processing
        background_tasks.add_task(
            process_document_task,
            document_id,
            document_type,
            file_path,
            file.filename,
            name,
            description,
            current_user['user_id'],
            current_user.get('team_id')
        )

        return DocumentUploadResponse(
            document_id=document_id,
            filename=file.filename,
            document_type=document_type,
            status="processing",
            message="Document uploaded successfully. Processing started."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/status/{document_id}", response_model=DocumentProcessingStatus)
async def get_processing_status(document_id: str, current_user: dict = Depends(require_team_membership)):
    """Get processing status for a document."""
    (settings, video_processor, rag_engine, gemini_client, report_generator,
     document_metadata, process_document_task, auth_service, knowledge_graph_service) = get_dependencies()

    # Check processor status first (for documents currently being processed)
    status = video_processor.get_status(document_id)

    if status:
        return DocumentProcessingStatus(
            document_id=document_id,
            status=status.get('status', 'unknown'),
            progress=status.get('progress', 0),
            message=status.get('error') or status.get('message'),
            total_segments=status.get('total_segments')
        )

    # Check if document is indexed in Qdrant (completed documents)
    segment_count = rag_engine.get_document_chunk_count(document_id)
    if segment_count > 0:
        return DocumentProcessingStatus(
            document_id=document_id,
            status='completed',
            progress=100,
            message=None,
            total_segments=segment_count
        )

    raise HTTPException(status_code=404, detail="Document not found")


@router.post("/chat", response_model=ChatResponse)
async def chat_with_documents(
    document_id: Optional[str] = Form(None),
    message: str = Form(...),
    conversation_history: str = Form("[]"),
    files: List[UploadFile] = File(default=[]),
    current_user: dict = Depends(require_team_membership)
):
    """Chat with the AI copilot. If document_id is provided, search is scoped to that
    document; otherwise it searches across the user's entire team corpus."""
    (settings, video_processor, rag_engine, gemini_client, report_generator,
     document_metadata, process_document_task, auth_service, knowledge_graph_service) = get_dependencies()

    try:
        # Parse conversation history
        conv_history = json.loads(conversation_history) if conversation_history else []

        # Process uploaded files if any (ad-hoc attachments, not indexed)
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

        # Search for relevant chunks - scoped to one document, or across the team's corpus
        relevant_segments = rag_engine.search_segments(
            query=message,
            document_id=document_id,
            team_id=current_user.get('team_id') if not document_id else None,
            top_k=15
        )

        if not relevant_segments and not file_contents:
            return ChatResponse(
                response="I couldn't find any relevant information in the knowledge base for your question.",
                sources=[],
                sources_used=0
            )

        # Enrich each chunk with its document name/type for citation building and prompt context
        metadata_cache = {}
        for seg in relevant_segments:
            seg_doc_id = seg.get('document_id')
            if seg_doc_id and seg_doc_id not in metadata_cache:
                metadata_cache[seg_doc_id] = rag_engine.get_document_metadata(seg_doc_id) or {}
            meta = metadata_cache.get(seg_doc_id, {})
            seg['document_name'] = meta.get('name', meta.get('filename', 'Unknown document'))

        # Generate response using Gemini (with ad-hoc files if provided)
        response_text = gemini_client.generate_response_with_files(
            query=message,
            context_segments=relevant_segments,
            conversation_history=conv_history,
            files=file_contents
        )

        # Build structured source citations (top 5)
        sources = [
            SourceReference(
                document_id=seg.get('document_id', ''),
                document_name=seg.get('document_name', 'Unknown document'),
                document_type=seg.get('document_type', 'video'),
                locator=format_locator(seg),
                start_time=seg.get('start_time'),
                end_time=seg.get('end_time'),
                page_number=seg.get('page_number'),
                sheet_name=seg.get('sheet_name'),
                row_range=seg.get('row_range'),
                text=seg['text'][:200] + "..." if len(seg['text']) > 200 else seg['text'],
                relevance_score=seg['score']
            )
            for seg in relevant_segments[:5]
        ]

        return ChatResponse(
            response=response_text,
            sources=sources,
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
    """Stream a video file with range request support (video-specific playback route)."""
    (settings, video_processor, rag_engine, gemini_client, report_generator,
     document_metadata, process_document_task, auth_service, knowledge_graph_service) = get_dependencies()

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


@router.get("/document/{document_id}/file")
async def get_document_file(
    document_id: str,
    current_user: dict = Depends(require_team_membership_flexible)
):
    """Serve the raw file for a non-video document (PDF/image), for viewers to render."""
    (settings, video_processor, rag_engine, gemini_client, report_generator,
     document_metadata, process_document_task, auth_service, knowledge_graph_service) = get_dependencies()

    metadata = rag_engine.get_document_metadata(document_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Document not found")

    filename = metadata.get('filename', '')
    ext = Path(filename).suffix.lower()
    file_path = video_processor.upload_dir / f"{document_id}{ext}"

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    media_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'

    def iterfile():
        with open(file_path, 'rb') as f:
            while chunk := f.read(1024 * 1024):
                yield chunk

    return StreamingResponse(iterfile(), media_type=media_type)


@router.get("/document/{document_id}/preview")
async def get_spreadsheet_preview(
    document_id: str,
    current_user: dict = Depends(require_team_membership)
):
    """Return a row preview (first 50 rows per sheet) for a spreadsheet document."""
    (settings, video_processor, rag_engine, gemini_client, report_generator,
     document_metadata, process_document_task, auth_service, knowledge_graph_service) = get_dependencies()

    metadata = rag_engine.get_document_metadata(document_id)
    if not metadata or metadata.get('document_type') != 'spreadsheet':
        raise HTTPException(status_code=404, detail="Spreadsheet preview not available for this document")

    filename = metadata.get('filename', '')
    ext = Path(filename).suffix.lower()
    file_path = video_processor.upload_dir / f"{document_id}{ext}"

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        if ext == '.csv':
            sheets = {"Sheet1": pd.read_csv(file_path, dtype=str).fillna("")}
        else:
            raw_sheets = pd.read_excel(file_path, sheet_name=None, dtype=str)
            sheets = {name: df.fillna("") for name, df in raw_sheets.items()}

        return {
            name: {
                "columns": [str(c) for c in df.columns],
                "rows": df.head(50).values.tolist(),
                "total_rows": len(df)
            }
            for name, df in sheets.items()
        }
    except Exception as e:
        logger.error(f"Failed to build spreadsheet preview for {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to read spreadsheet")


@router.get("/documents", response_model=list[DocumentInfo])
async def list_documents(current_user: dict = Depends(require_team_membership)):
    """Get list of all processed documents visible to the current user's team."""
    (settings, video_processor, rag_engine, gemini_client, report_generator,
     document_metadata, process_document_task, auth_service, knowledge_graph_service) = get_dependencies()

    try:
        documents = []
        team_id = current_user.get('team_id') if current_user.get('role') != 'admin' else None
        metadata_list = rag_engine.list_all_document_metadata(team_id=team_id)

        for metadata in metadata_list:
            author_name = None
            author_id = metadata.get('author_id')
            if author_id:
                try:
                    user = auth_service.get_user_by_id(author_id)
                    if user:
                        author_name = user.get('full_name')
                except Exception as e:
                    logger.warning(f"Failed to fetch author name for user {author_id}: {e}")

            documents.append(DocumentInfo(
                document_id=metadata['document_id'],
                document_type=metadata.get('document_type', 'video'),
                filename=metadata.get('filename', ''),
                name=metadata.get('name', metadata.get('filename', '')),
                description=metadata.get('description'),
                upload_date=datetime.fromisoformat(metadata['upload_date']) if 'upload_date' in metadata else datetime.now(),
                total_segments=metadata.get('total_segments', 0),
                duration=metadata.get('duration'),
                status='completed',
                author_name=author_name
            ))

        return sorted(documents, key=lambda x: x.upload_date, reverse=True)

    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to list documents")


@router.post("/document/{document_id}/report")
async def generate_document_report(
    document_id: str,
    request: ReportGenerationRequest = ReportGenerationRequest(),
    current_user: dict = Depends(require_team_membership)
):
    """Generate a PDF evidence-pack report for a document with optional additional instructions."""
    (settings, video_processor, rag_engine, gemini_client, report_generator,
     document_metadata, process_document_task, auth_service, knowledge_graph_service) = get_dependencies()

    try:
        metadata = rag_engine.get_document_metadata(document_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Document not found")

        results = rag_engine.qdrant_client.scroll(
            collection_name=rag_engine.collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="document_id", match=MatchValue(value=document_id)),
                    FieldCondition(key="chunk_type", match=MatchValue(value="regular"))
                ]
            ),
            limit=10000,
            with_payload=True,
            with_vectors=False
        )

        segments = [r.payload for r in results[0]]
        segments.sort(key=lambda x: (x.get('page_number') is None, x.get('page_number', 0), x.get('start_time') or 0))

        report_path = await report_generator.generate_report(
            document_id=document_id,
            document_name=metadata.get('name', metadata.get('filename', 'Untitled')),
            document_description=metadata.get('description', ''),
            duration=metadata.get('duration'),
            segments=segments,
            additional_instructions=request.additional_instructions
        )

        def iterfile():
            with open(report_path, 'rb') as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk

        return StreamingResponse(
            iterfile(),
            media_type='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{metadata.get("name", "document")}_report.pdf"'
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate report: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@router.post("/document/{document_id}/diagram", response_model=DiagramGenerationResponse)
async def generate_document_diagram(
    document_id: str,
    request: DiagramGenerationRequest,
    current_user: dict = Depends(require_team_membership)
):
    """Generate a Mermaid diagram based on one document's content and a user query."""
    (settings, video_processor, rag_engine, gemini_client, report_generator,
     document_metadata, process_document_task, auth_service, knowledge_graph_service) = get_dependencies()

    try:
        metadata = rag_engine.get_document_metadata(document_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Document not found")

        results = rag_engine.qdrant_client.scroll(
            collection_name=rag_engine.collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="document_id", match=MatchValue(value=document_id)),
                    FieldCondition(key="chunk_type", match=MatchValue(value="regular"))
                ]
            ),
            limit=10000,
            with_payload=True,
            with_vectors=False
        )

        segments = [r.payload for r in results[0]]
        segments.sort(key=lambda x: (x.get('page_number') is None, x.get('page_number', 0), x.get('start_time') or 0))

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


@router.delete("/document/{document_id}")
async def delete_document(document_id: str, current_user: dict = Depends(get_current_active_user)):
    """Delete a document and all its data (author, team lead, or admin only)."""
    (settings, video_processor, rag_engine, gemini_client, report_generator,
     document_metadata, process_document_task, auth_service, knowledge_graph_service) = get_dependencies()

    try:
        metadata = rag_engine.get_document_metadata(document_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Document not found")

        if not check_video_permission(metadata, current_user):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to delete this document"
            )

        rag_engine.delete_document_chunks(document_id)
        rag_engine.delete_document_metadata(document_id)

        try:
            knowledge_graph_service.delete_document(document_id)
        except Exception as e:
            logger.warning(f"Failed to prune knowledge graph for {document_id}: {e}")

        for existing_file in video_processor.upload_dir.glob(f"{document_id}.*"):
            existing_file.unlink()

        if document_id in document_metadata:
            del document_metadata[document_id]

        logger.info(f"Deleted document {document_id} by user {current_user['user_id']}")

        return {"message": "Document deleted successfully", "document_id": document_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")
