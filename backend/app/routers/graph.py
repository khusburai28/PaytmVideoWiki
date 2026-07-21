from fastapi import APIRouter, HTTPException, Depends
import logging

from app.models.graph_schemas import GraphResponse, EntityDetailResponse, GraphNode, GraphEdge, DocumentRef
from app.middleware.auth import require_team_membership

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graph", tags=["graph"])


def get_dependencies():
    from app.main import knowledge_graph_service, rag_engine
    return knowledge_graph_service, rag_engine


@router.get("", response_model=GraphResponse)
async def get_graph(current_user: dict = Depends(require_team_membership)):
    """Return the full extracted knowledge graph (nodes = entities, edges = relationships)."""
    knowledge_graph_service, _ = get_dependencies()
    data = knowledge_graph_service.get_graph()
    return GraphResponse(
        nodes=[GraphNode(**n) for n in data["nodes"]],
        edges=[GraphEdge(**e) for e in data["edges"]]
    )


@router.get("/entity/{entity_id}", response_model=EntityDetailResponse)
async def get_entity_detail(entity_id: str, current_user: dict = Depends(require_team_membership)):
    """Return one entity's neighborhood plus the documents it was extracted from (provenance)."""
    knowledge_graph_service, rag_engine = get_dependencies()
    detail = knowledge_graph_service.get_entity_detail(entity_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Entity not found")

    documents = []
    for doc_id in detail["node"].get("document_ids", []):
        meta = rag_engine.get_document_metadata(doc_id)
        if meta:
            documents.append(DocumentRef(
                document_id=doc_id,
                document_name=meta.get("name", meta.get("filename", doc_id)),
                document_type=meta.get("document_type", "video")
            ))

    return EntityDetailResponse(
        node=GraphNode(**detail["node"]),
        neighbors=[GraphNode(**n) for n in detail["neighbors"]],
        edges=[GraphEdge(id=f"e{i}", **e) for i, e in enumerate(detail["edges"])],
        documents=documents
    )


@router.get("/document/{document_id}", response_model=GraphResponse)
async def get_document_subgraph(document_id: str, current_user: dict = Depends(require_team_membership)):
    """Return only the entities/relationships extracted from one document (per-document provenance)."""
    knowledge_graph_service, _ = get_dependencies()
    data = knowledge_graph_service.get_document_subgraph(document_id)
    return GraphResponse(
        nodes=[GraphNode(**n) for n in data["nodes"]],
        edges=[GraphEdge(**e) for e in data["edges"]]
    )
