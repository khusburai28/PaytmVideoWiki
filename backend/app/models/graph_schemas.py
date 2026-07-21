from pydantic import BaseModel
from typing import List, Optional, Literal

EntityType = Literal[
    "equipment", "personnel", "date", "regulation",
    "process_parameter", "location", "organization",
    "incident", "work_order"
]


class GraphNode(BaseModel):
    id: str
    label: str
    type: EntityType
    normalized_id: Optional[str] = None
    mention_count: int = 0
    document_ids: List[str] = []
    document_names: List[str] = []


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relation: str
    document_id: Optional[str] = None


class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]


class DocumentRef(BaseModel):
    document_id: str
    document_name: str
    document_type: str


class EntityDetailResponse(BaseModel):
    node: GraphNode
    neighbors: List[GraphNode]
    edges: List[GraphEdge]
    documents: List[DocumentRef]
