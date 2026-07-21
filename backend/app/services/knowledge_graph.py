import json
import re
import threading
from pathlib import Path
from typing import Dict, List, Optional, Literal
import logging

import networkx as nx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

EntityType = Literal[
    "equipment", "personnel", "date", "regulation",
    "process_parameter", "location", "organization",
    "incident", "work_order"
]


class ExtractedEntity(BaseModel):
    name: str
    type: EntityType
    normalized_id: Optional[str] = None


class ExtractedRelationship(BaseModel):
    source: str
    target: str
    relation: str


class ExtractionResult(BaseModel):
    entities: List[ExtractedEntity] = []
    relationships: List[ExtractedRelationship] = []


# Fallback regex for common industrial equipment tag formats (e.g. "P-204", "B-102A"),
# used only if Gemini's structured extraction call fails, so the graph is never empty.
_TAG_PATTERN = re.compile(r"\b[A-Z]{1,3}-\d{2,4}[A-Z]?\b")

EXTRACTION_TEXT_LIMIT = 6000


class KnowledgeGraphService:
    """A single corpus-wide entity/relationship graph, backed by networkx and persisted
    as JSON. No separate graph database - deliberately avoids adding new infra."""

    def __init__(self, gemini_client, storage_path: str = "./data/knowledge_graph.json"):
        self.gemini_client = gemini_client
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.graph = nx.MultiDiGraph()
        self._load()

    def _load(self):
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r") as f:
                    data = json.load(f)
                self.graph = nx.node_link_graph(data, directed=True, multigraph=True)
                logger.info(
                    f"Loaded knowledge graph with {self.graph.number_of_nodes()} nodes, "
                    f"{self.graph.number_of_edges()} edges"
                )
            except Exception as e:
                logger.warning(f"Failed to load existing knowledge graph, starting fresh: {e}")
                self.graph = nx.MultiDiGraph()

    def _save(self):
        data = nx.node_link_data(self.graph)
        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    @staticmethod
    def _node_key(name: str, entity_type: str, normalized_id: Optional[str] = None) -> str:
        if normalized_id:
            return f"{entity_type}:{normalized_id.strip().upper()}"
        return f"{entity_type}:{name.strip().lower()}"

    def extract_and_merge(
        self,
        document_id: str,
        document_name: str,
        document_type: str,
        full_text: str
    ) -> ExtractionResult:
        """Extract entities/relationships from a document's text and merge them into the
        persisted graph. Merging by normalized_id (or lowercased name+type) is what makes
        the same equipment tag mentioned across a PDF, spreadsheet, and image collapse into
        one shared node instead of duplicates."""
        extraction = self._extract_entities(full_text, document_type)

        if not extraction.entities and not extraction.relationships:
            extraction = self._fallback_extract(full_text)

        with self._lock:
            name_to_key = {}
            for entity in extraction.entities:
                key = self._node_key(entity.name, entity.type, entity.normalized_id)
                name_to_key[entity.name] = key

                if self.graph.has_node(key):
                    node = self.graph.nodes[key]
                    node["mention_count"] = node.get("mention_count", 0) + 1
                    doc_ids = set(node.get("document_ids", []))
                    doc_ids.add(document_id)
                    node["document_ids"] = list(doc_ids)
                    doc_names = set(node.get("document_names", []))
                    doc_names.add(document_name)
                    node["document_names"] = list(doc_names)
                else:
                    self.graph.add_node(
                        key,
                        label=entity.normalized_id or entity.name,
                        type=entity.type,
                        normalized_id=entity.normalized_id,
                        mention_count=1,
                        document_ids=[document_id],
                        document_names=[document_name]
                    )

            for rel in extraction.relationships:
                source_key = name_to_key.get(rel.source)
                target_key = name_to_key.get(rel.target)
                if not source_key or not target_key:
                    continue
                self.graph.add_edge(source_key, target_key, relation=rel.relation, document_id=document_id)

            self._save()

        logger.info(
            f"Merged {len(extraction.entities)} entities, {len(extraction.relationships)} "
            f"relationships from document {document_id}"
        )
        return extraction

    def _extract_entities(self, text: str, document_type: str) -> ExtractionResult:
        prompt = f"""Extract industrial knowledge entities and relationships from the following {document_type} document text.

Entity types: equipment (asset tags like pumps/boilers/valves), personnel (people mentioned by name or role),
date (specific dates or time periods), regulation (standards/codes like OISD, PESO, Factory Act clauses),
process_parameter (measured values like pressure, temperature, flow rate), location (plant areas, buildings),
organization (companies, vendors, departments), incident (failures, accidents, near-misses), work_order (maintenance/repair tickets).

For equipment, if there is a short tag code (e.g. "P-204", "B-102"), put it in normalized_id.

Relationships must reference entities using their exact "name" field as extracted above
(e.g. source="P-204", target="John Smith", relation="inspected_by").

Only extract entities that are clearly and specifically mentioned - do not invent data. If nothing
qualifies, return empty lists.

TEXT:
{text[:EXTRACTION_TEXT_LIMIT]}
"""
        try:
            raw = self.gemini_client.generate_structured(prompt, ExtractionResult)
            return ExtractionResult.model_validate_json(raw)
        except Exception as e:
            logger.warning(f"Structured entity extraction failed, will use regex fallback: {e}")
            return ExtractionResult()

    def _fallback_extract(self, text: str) -> ExtractionResult:
        """Regex-based equipment tag extraction, used only if Gemini structured output fails."""
        tags = sorted(set(_TAG_PATTERN.findall(text)))
        entities = [ExtractedEntity(name=tag, type="equipment", normalized_id=tag) for tag in tags]
        return ExtractionResult(entities=entities, relationships=[])

    def get_graph(self) -> Dict:
        with self._lock:
            nodes = [{"id": node_id, **data} for node_id, data in self.graph.nodes(data=True)]
            edges = [
                {"id": f"e{idx}", "source": u, "target": v, **data}
                for idx, (u, v, data) in enumerate(self.graph.edges(data=True))
            ]
            return {"nodes": nodes, "edges": edges}

    def get_entity_detail(self, entity_id: str) -> Optional[Dict]:
        with self._lock:
            if not self.graph.has_node(entity_id):
                return None
            node = {"id": entity_id, **self.graph.nodes[entity_id]}
            neighbor_ids = set(self.graph.successors(entity_id)) | set(self.graph.predecessors(entity_id))
            neighbors = [{"id": n, **self.graph.nodes[n]} for n in neighbor_ids]
            edges = [
                {"source": u, "target": v, **data}
                for u, v, data in self.graph.edges(data=True)
                if u == entity_id or v == entity_id
            ]
            return {"node": node, "neighbors": neighbors, "edges": edges}

    def get_document_subgraph(self, document_id: str) -> Dict:
        with self._lock:
            nodes = [
                {"id": node_id, **data}
                for node_id, data in self.graph.nodes(data=True)
                if document_id in data.get("document_ids", [])
            ]
            node_ids = {n["id"] for n in nodes}
            edges = [
                {"id": f"e{idx}", "source": u, "target": v, **data}
                for idx, (u, v, data) in enumerate(self.graph.edges(data=True))
                if u in node_ids and v in node_ids
            ]
            return {"nodes": nodes, "edges": edges}

    def delete_document(self, document_id: str):
        """Remove a document's contribution from the graph: drop its mention from every
        node, and delete nodes/edges that end up with no remaining documents."""
        with self._lock:
            nodes_to_remove = []
            for node_id, data in self.graph.nodes(data=True):
                doc_ids = set(data.get("document_ids", []))
                if document_id in doc_ids:
                    doc_ids.discard(document_id)
                    if doc_ids:
                        data["document_ids"] = list(doc_ids)
                        data["document_names"] = [
                            n for n in data.get("document_names", [])
                        ]
                    else:
                        nodes_to_remove.append(node_id)

            self.graph.remove_nodes_from(nodes_to_remove)

            edges_to_remove = [
                (u, v, k) for u, v, k, data in self.graph.edges(keys=True, data=True)
                if data.get("document_id") == document_id
            ]
            self.graph.remove_edges_from(edges_to_remove)

            self._save()
