from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, PayloadSchemaType
from google import genai
from typing import List, Dict, Optional
from datetime import datetime
import logging
import uuid

logger = logging.getLogger(__name__)


class RAGEngine:
    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        collection_name: str = "document_chunks",
        metadata_collection_name: str = "document_metadata",
        gemini_api_key: str = None,
        embedding_model: str = "gemini-embedding-001",
        gemini_model: str = "gemini-2.5-flash"
    ):
        """Initialize RAG engine with Qdrant and Gemini embedding model."""
        self.collection_name = collection_name
        self.metadata_collection_name = metadata_collection_name
        self.embedding_model_name = embedding_model
        self.gemini_model_name = gemini_model

        # Initialize Qdrant client
        logger.info(f"Connecting to Qdrant at {qdrant_host}:{qdrant_port}")
        self.qdrant_client = QdrantClient(host=qdrant_host, port=qdrant_port)

        # Initialize Gemini client for embeddings + generation
        logger.info(f"Initializing Gemini embedding model: {embedding_model}")
        self.genai_client = genai.Client(api_key=gemini_api_key)

        # Gemini embedding dimension is 3072 for gemini-embedding-001
        self.embedding_dim = 3072

        # Create collections if they don't exist
        self._ensure_collection_exists()
        self._ensure_metadata_collection_exists()

    def _ensure_collection_exists(self):
        """Create Qdrant chunk collection (and payload indexes) if it doesn't exist."""
        try:
            collections = self.qdrant_client.get_collections().collections
            collection_names = [col.name for col in collections]

            if self.collection_name not in collection_names:
                logger.info(f"Creating collection: {self.collection_name}")
                self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.embedding_dim,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Collection created: {self.collection_name}")
            else:
                logger.info(f"Collection already exists: {self.collection_name}")

            # Payload indexes make document_id/team_id/document_type filtering fast
            # once the corpus spans many documents and teams (cross-corpus search).
            for field_name in ("document_id", "team_id", "document_type"):
                try:
                    self.qdrant_client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name=field_name,
                        field_schema=PayloadSchemaType.KEYWORD
                    )
                except Exception:
                    # Index already exists - safe to ignore.
                    pass
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            raise

    def _ensure_metadata_collection_exists(self):
        """Create Qdrant metadata collection if it doesn't exist."""
        try:
            collections = self.qdrant_client.get_collections().collections
            collection_names = [col.name for col in collections]

            if self.metadata_collection_name not in collection_names:
                logger.info(f"Creating metadata collection: {self.metadata_collection_name}")
                # Metadata collection doesn't need vectors, just payload storage
                self.qdrant_client.create_collection(
                    collection_name=self.metadata_collection_name,
                    vectors_config=VectorParams(
                        size=1,  # Minimal vector size since we only use payload
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Metadata collection created: {self.metadata_collection_name}")
            else:
                logger.info(f"Metadata collection already exists: {self.metadata_collection_name}")

            for field_name in ("team_id", "document_type"):
                try:
                    self.qdrant_client.create_payload_index(
                        collection_name=self.metadata_collection_name,
                        field_name=field_name,
                        field_schema=PayloadSchemaType.KEYWORD
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Failed to create metadata collection: {e}")
            raise

    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using Gemini API."""
        try:
            result = self.genai_client.models.embed_content(
                model=self.embedding_model_name,
                contents=text
            )
            return result.embeddings[0].values
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    def _generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts in batch (faster)."""
        try:
            # Gemini API supports batch embedding
            result = self.genai_client.models.embed_content(
                model=self.embedding_model_name,
                contents=texts
            )
            return [emb.values for emb in result.embeddings]
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            raise

    def _generate_derived_chunks(self, full_text: str, document_type: str) -> List[Dict]:
        """Generate a summary and FAQ chunk from a document's combined text, regardless of type."""
        derived_chunks = []

        summary_prompt = f"""Summarize this {document_type} document in 2-3 concise sentences. Focus on the main topic and key points:

{full_text[:3000]}"""

        try:
            result = self.genai_client.models.generate_content(
                model=self.gemini_model_name,
                contents=summary_prompt
            )
            derived_chunks.append({
                "text": f"SUMMARY: {result.text}",
                "confidence": 1.0,
                "chunk_type": "summary"
            })
            logger.info("Generated summary chunk")
        except Exception as e:
            logger.warning(f"Failed to generate summary: {e}")

        # Roughly one FAQ per 2000 characters of source text, bounded 3-10
        faq_count = min(max(len(full_text) // 2000, 3), 10)

        faq_prompt = f"""Based on this {document_type} document, generate {faq_count} frequently asked questions and brief answers. Format as "Q: ... A: ..."

{full_text[:4000]}"""

        try:
            result = self.genai_client.models.generate_content(
                model=self.gemini_model_name,
                contents=faq_prompt
            )
            derived_chunks.append({
                "text": f"FAQ: {result.text}",
                "confidence": 1.0,
                "chunk_type": "faq"
            })
            logger.info(f"Generated FAQ chunk with {faq_count} questions")
        except Exception as e:
            logger.warning(f"Failed to generate FAQs: {e}")

        return derived_chunks

    def index_document_chunks(
        self,
        document_id: str,
        document_type: str,
        segments: List[Dict],
        team_id: Optional[str] = None,
        author_id: Optional[str] = None,
        generate_derived: bool = True
    ):
        """Index a document's chunks into Qdrant. `segments` is a list of dicts with at least
        a 'text' key, plus whichever locator fields apply to the document type
        (start_time/end_time for video, page_number for PDF, sheet_name/row_range for spreadsheets)."""
        try:
            logger.info(f"Indexing {len(segments)} chunks for {document_type} document {document_id}")

            derived_chunks = []
            if generate_derived and segments:
                full_text = " ".join(seg['text'] for seg in segments)
                logger.info("Generating derived chunks (summary + FAQs)...")
                derived_chunks = self._generate_derived_chunks(full_text, document_type)

            all_segments = segments + derived_chunks
            logger.info(f"Total chunks to index: {len(all_segments)} ({len(segments)} regular + {len(derived_chunks)} derived)")

            texts = [segment['text'] for segment in all_segments]

            logger.info("Generating embeddings in batches...")
            all_embeddings = []
            batch_size = 100

            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                logger.info(f"Processing embedding batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}")
                batch_embeddings = self._generate_embeddings_batch(batch_texts)
                all_embeddings.extend(batch_embeddings)

            points = []
            for idx, (segment, embedding) in enumerate(zip(all_segments, all_embeddings)):
                point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload={
                        "document_id": document_id,
                        "document_type": document_type,
                        "team_id": team_id,
                        "author_id": author_id,
                        "text": segment['text'],
                        "start_time": segment.get('start_time'),
                        "end_time": segment.get('end_time'),
                        "page_number": segment.get('page_number'),
                        "sheet_name": segment.get('sheet_name'),
                        "row_range": segment.get('row_range'),
                        "confidence": segment.get('confidence', 0.0),
                        "segment_index": idx,
                        "chunk_type": segment.get('chunk_type', 'regular')
                    }
                )
                points.append(point)

            logger.info(f"Uploading {len(points)} vectors to Qdrant...")
            qdrant_batch_size = 100
            for i in range(0, len(points), qdrant_batch_size):
                batch = points[i:i + qdrant_batch_size]
                self.qdrant_client.upsert(
                    collection_name=self.collection_name,
                    points=batch
                )

            logger.info(f"Successfully indexed {len(all_segments)} chunks for document {document_id}")
            return all_segments

        except Exception as e:
            logger.error(f"Failed to index chunks: {e}")
            raise

    def search_segments(
        self,
        query: str,
        document_id: Optional[str] = None,
        team_id: Optional[str] = None,
        top_k: int = 5
    ) -> List[Dict]:
        """Search for relevant chunks. If document_id is given, search is scoped to that
        document (legacy single-document mode). Otherwise, if team_id is given, search spans
        every document belonging to that team (corpus-wide copilot mode). If neither is given,
        search spans the entire collection (admin/global mode)."""
        try:
            query_embedding = self._generate_embedding(query)

            must_conditions = []
            if document_id:
                must_conditions.append(
                    FieldCondition(key="document_id", match=MatchValue(value=document_id))
                )
            elif team_id:
                must_conditions.append(
                    FieldCondition(key="team_id", match=MatchValue(value=team_id))
                )

            search_filter = Filter(must=must_conditions) if must_conditions else None

            search_results = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=top_k
            )

            results = []
            for hit in search_results:
                results.append({
                    "document_id": hit.payload.get('document_id'),
                    "document_type": hit.payload.get('document_type', 'video'),
                    "text": hit.payload['text'],
                    "start_time": hit.payload.get('start_time'),
                    "end_time": hit.payload.get('end_time'),
                    "page_number": hit.payload.get('page_number'),
                    "sheet_name": hit.payload.get('sheet_name'),
                    "row_range": hit.payload.get('row_range'),
                    "confidence": hit.payload.get('confidence', 0.0),
                    "score": hit.score,
                    "segment_index": hit.payload.get('segment_index', 0)
                })

            logger.info(f"Found {len(results)} relevant chunks for query: {query[:50]}...")
            return results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    def delete_document_chunks(self, document_id: str):
        """Delete all chunks for a specific document."""
        try:
            self.qdrant_client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id)
                        )
                    ]
                )
            )
            logger.info(f"Deleted all chunks for document: {document_id}")
        except Exception as e:
            logger.error(f"Failed to delete chunks: {e}")
            raise

    def get_document_chunk_count(self, document_id: str) -> int:
        """Get count of indexed chunks for a document."""
        try:
            result = self.qdrant_client.count(
                collection_name=self.collection_name,
                count_filter=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id)
                        )
                    ]
                )
            )
            return result.count
        except Exception as e:
            logger.error(f"Failed to count chunks: {e}")
            return 0

    def list_indexed_documents(self) -> List[str]:
        """Get list of all indexed document IDs."""
        try:
            document_ids = set()
            offset = None

            while True:
                records, offset = self.qdrant_client.scroll(
                    collection_name=self.collection_name,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False
                )

                for record in records:
                    document_ids.add(record.payload['document_id'])

                if offset is None:
                    break

            return list(document_ids)

        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            return []

    def save_document_metadata(
        self,
        document_id: str,
        document_type: str,
        name: str,
        description: str,
        filename: str,
        total_segments: int,
        author_id: str,
        team_id: Optional[str] = None,
        duration: Optional[float] = None,
        extra: Optional[Dict] = None
    ):
        """Save document metadata to Qdrant metadata collection. `extra` can carry
        type-specific fields (e.g. page_count for PDFs, sheet_names for spreadsheets)."""
        try:
            payload = {
                "document_id": document_id,
                "document_type": document_type,
                "name": name,
                "description": description,
                "duration": duration,
                "filename": filename,
                "total_segments": total_segments,
                "upload_date": datetime.now().isoformat(),
                "author_id": author_id,
                "team_id": team_id
            }
            if extra:
                payload.update(extra)

            point = PointStruct(
                id=document_id,
                vector=[0.0],  # Dummy vector since we only use payload
                payload=payload
            )

            self.qdrant_client.upsert(
                collection_name=self.metadata_collection_name,
                points=[point]
            )
            logger.info(f"Saved metadata for document: {document_id} - {name}")
        except Exception as e:
            logger.error(f"Failed to save document metadata: {e}")
            raise

    def get_document_metadata(self, document_id: str) -> Optional[Dict]:
        """Get document metadata from Qdrant metadata collection."""
        try:
            result = self.qdrant_client.retrieve(
                collection_name=self.metadata_collection_name,
                ids=[document_id],
                with_payload=True,
                with_vectors=False
            )

            if result and len(result) > 0:
                return result[0].payload
            return None
        except Exception as e:
            logger.error(f"Failed to get document metadata: {e}")
            return None

    def list_all_document_metadata(self, team_id: Optional[str] = None) -> List[Dict]:
        """Get metadata for all documents, optionally scoped to a team."""
        try:
            all_metadata = []
            offset = None
            scroll_filter = None
            if team_id:
                scroll_filter = Filter(
                    must=[FieldCondition(key="team_id", match=MatchValue(value=team_id))]
                )

            while True:
                records, offset = self.qdrant_client.scroll(
                    collection_name=self.metadata_collection_name,
                    scroll_filter=scroll_filter,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False
                )

                for record in records:
                    all_metadata.append(record.payload)

                if offset is None:
                    break

            logger.info(f"Retrieved metadata for {len(all_metadata)} documents")
            return all_metadata

        except Exception as e:
            logger.error(f"Failed to list document metadata: {e}")
            return []

    def delete_document_metadata(self, document_id: str):
        """Delete document metadata from Qdrant metadata collection."""
        try:
            self.qdrant_client.delete(
                collection_name=self.metadata_collection_name,
                points_selector=[document_id]
            )
            logger.info(f"Deleted metadata for document: {document_id}")
        except Exception as e:
            logger.error(f"Failed to delete document metadata: {e}")
            raise
