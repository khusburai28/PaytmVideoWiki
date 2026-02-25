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
        collection_name: str = "video_transcripts",
        metadata_collection_name: str = "video_metadata",
        gemini_api_key: str = None,
        embedding_model: str = "gemini-embedding-004"
    ):
        """Initialize RAG engine with Qdrant and Gemini embedding model."""
        self.collection_name = collection_name
        self.metadata_collection_name = metadata_collection_name
        self.embedding_model_name = embedding_model

        # Initialize Qdrant client
        logger.info(f"Connecting to Qdrant at {qdrant_host}:{qdrant_port}")
        self.qdrant_client = QdrantClient(host=qdrant_host, port=qdrant_port)

        # Initialize Gemini client for embeddings
        logger.info(f"Initializing Gemini embedding model: {embedding_model}")
        self.genai_client = genai.Client(api_key=gemini_api_key)

        # Gemini embedding dimension is 3072 for gemini-embedding-001
        self.embedding_dim = 3072

        # Create collections if they don't exist
        self._ensure_collection_exists()
        self._ensure_metadata_collection_exists()

    def _ensure_collection_exists(self):
        """Create Qdrant collection if it doesn't exist."""
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

    def _generate_derived_chunks(self, segments: List[Dict], video_duration: float) -> List[Dict]:
        """Generate summary and FAQ chunks from transcription."""
        derived_chunks = []

        # Get full transcript
        full_transcript = " ".join([seg['text'] for seg in segments])

        # Create summary chunk
        summary_prompt = f"""Summarize this video transcript in 2-3 concise sentences. Focus on the main topic and key points:

{full_transcript[:3000]}"""  # Limit to first 3000 chars for speed

        try:
            result = self.genai_client.models.generate_content(
                model=self.embedding_model_name.replace('embedding', '1.5-flash'),  # Use flash model for generation
                contents=summary_prompt
            )
            summary_text = f"VIDEO SUMMARY: {result.text}"
            derived_chunks.append({
                "text": summary_text,
                "start_time": 0,
                "end_time": video_duration,
                "confidence": 1.0,
                "chunk_type": "summary"
            })
            logger.info(f"Generated summary chunk")
        except Exception as e:
            logger.warning(f"Failed to generate summary: {e}")

        # Generate FAQs based on video length
        # Formula: 1 FAQ per 10 minutes, minimum 3, maximum 10
        faq_count = min(max(int(video_duration / 600), 3), 10)

        faq_prompt = f"""Based on this video transcript, generate {faq_count} frequently asked questions and brief answers. Format as "Q: ... A: ..."

{full_transcript[:4000]}"""

        try:
            result = self.genai_client.models.generate_content(
                model=self.embedding_model_name.replace('embedding', '1.5-flash'),
                contents=faq_prompt
            )
            faq_text = f"VIDEO FAQ: {result.text}"
            derived_chunks.append({
                "text": faq_text,
                "start_time": 0,
                "end_time": video_duration,
                "confidence": 1.0,
                "chunk_type": "faq"
            })
            logger.info(f"Generated FAQ chunk with {faq_count} questions")
        except Exception as e:
            logger.warning(f"Failed to generate FAQs: {e}")

        return derived_chunks

    def index_video_segments(self, video_id: str, segments: List[Dict], video_duration: float = None):
        """Index video transcript segments into Qdrant."""
        try:
            logger.info(f"Indexing {len(segments)} segments for video {video_id}")

            # Generate derived chunks (summary and FAQs)
            derived_chunks = []
            if video_duration:
                logger.info("Generating derived chunks (summary + FAQs)...")
                derived_chunks = self._generate_derived_chunks(segments, video_duration)

            # Combine regular segments with derived chunks
            all_segments = segments + derived_chunks
            logger.info(f"Total chunks to index: {len(all_segments)} ({len(segments)} regular + {len(derived_chunks)} derived)")

            # Extract all texts for batch embedding
            texts = [segment['text'] for segment in all_segments]

            # Generate embeddings in batches for speed
            logger.info(f"Generating embeddings in batches...")
            all_embeddings = []
            batch_size = 100  # Gemini API batch limit

            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                logger.info(f"Processing embedding batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}")
                batch_embeddings = self._generate_embeddings_batch(batch_texts)
                all_embeddings.extend(batch_embeddings)

            # Prepare points for insertion
            points = []
            for idx, (segment, embedding) in enumerate(zip(all_segments, all_embeddings)):
                point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload={
                        "video_id": video_id,
                        "text": segment['text'],
                        "start_time": segment['start_time'],
                        "end_time": segment['end_time'],
                        "confidence": segment.get('confidence', 0.0),
                        "segment_index": idx,
                        "chunk_type": segment.get('chunk_type', 'regular')
                    }
                )
                points.append(point)

            # Upload points to Qdrant in batches
            logger.info(f"Uploading {len(points)} vectors to Qdrant...")
            qdrant_batch_size = 100
            for i in range(0, len(points), qdrant_batch_size):
                batch = points[i:i + qdrant_batch_size]
                self.qdrant_client.upsert(
                    collection_name=self.collection_name,
                    points=batch
                )

            logger.info(f"Successfully indexed {len(all_segments)} chunks for video {video_id}")

        except Exception as e:
            logger.error(f"Failed to index segments: {e}")
            raise

    def search_segments(
        self,
        video_id: str,
        query: str,
        top_k: int = 5
    ) -> List[Dict]:
        """Search for relevant video segments based on query."""
        try:
            # Generate query embedding using Gemini
            query_embedding = self._generate_embedding(query)

            # Search in Qdrant with video_id filter
            search_results = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="video_id",
                            match=MatchValue(value=video_id)
                        )
                    ]
                ),
                limit=top_k
            )

            # Format results
            results = []
            for hit in search_results:
                results.append({
                    "text": hit.payload['text'],
                    "start_time": hit.payload['start_time'],
                    "end_time": hit.payload['end_time'],
                    "confidence": hit.payload.get('confidence', 0.0),
                    "score": hit.score,
                    "segment_index": hit.payload.get('segment_index', 0)
                })

            logger.info(f"Found {len(results)} relevant segments for query: {query[:50]}...")
            return results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    def delete_video_segments(self, video_id: str):
        """Delete all segments for a specific video."""
        try:
            self.qdrant_client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="video_id",
                            match=MatchValue(value=video_id)
                        )
                    ]
                )
            )
            logger.info(f"Deleted all segments for video: {video_id}")
        except Exception as e:
            logger.error(f"Failed to delete segments: {e}")
            raise

    def get_video_segment_count(self, video_id: str) -> int:
        """Get count of indexed segments for a video."""
        try:
            result = self.qdrant_client.count(
                collection_name=self.collection_name,
                count_filter=Filter(
                    must=[
                        FieldCondition(
                            key="video_id",
                            match=MatchValue(value=video_id)
                        )
                    ]
                )
            )
            return result.count
        except Exception as e:
            logger.error(f"Failed to count segments: {e}")
            return 0

    def list_indexed_videos(self) -> List[str]:
        """Get list of all indexed video IDs."""
        try:
            # Scroll through all points and extract unique video IDs
            video_ids = set()
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
                    video_ids.add(record.payload['video_id'])

                if offset is None:
                    break

            return list(video_ids)

        except Exception as e:
            logger.error(f"Failed to list videos: {e}")
            return []

    def save_video_metadata(
        self,
        video_id: str,
        name: str,
        description: str,
        duration: float,
        filename: str,
        total_segments: int
    ):
        """Save video metadata to Qdrant metadata collection."""
        try:
            point = PointStruct(
                id=video_id,
                vector=[0.0],  # Dummy vector since we only use payload
                payload={
                    "video_id": video_id,
                    "name": name,
                    "description": description,
                    "duration": duration,
                    "filename": filename,
                    "total_segments": total_segments,
                    "upload_date": datetime.now().isoformat()
                }
            )

            self.qdrant_client.upsert(
                collection_name=self.metadata_collection_name,
                points=[point]
            )
            logger.info(f"Saved metadata for video: {video_id} - {name}")
        except Exception as e:
            logger.error(f"Failed to save video metadata: {e}")
            raise

    def get_video_metadata(self, video_id: str) -> Optional[Dict]:
        """Get video metadata from Qdrant metadata collection."""
        try:
            result = self.qdrant_client.retrieve(
                collection_name=self.metadata_collection_name,
                ids=[video_id],
                with_payload=True,
                with_vectors=False
            )

            if result and len(result) > 0:
                return result[0].payload
            return None
        except Exception as e:
            logger.error(f"Failed to get video metadata: {e}")
            return None

    def list_all_video_metadata(self) -> List[Dict]:
        """Get metadata for all videos."""
        try:
            all_metadata = []
            offset = None

            while True:
                records, offset = self.qdrant_client.scroll(
                    collection_name=self.metadata_collection_name,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False
                )

                for record in records:
                    all_metadata.append(record.payload)

                if offset is None:
                    break

            logger.info(f"Retrieved metadata for {len(all_metadata)} videos")
            return all_metadata

        except Exception as e:
            logger.error(f"Failed to list video metadata: {e}")
            return []

    def delete_video_metadata(self, video_id: str):
        """Delete video metadata from Qdrant metadata collection."""
        try:
            self.qdrant_client.delete(
                collection_name=self.metadata_collection_name,
                points_selector=[video_id]
            )
            logger.info(f"Deleted metadata for video: {video_id}")
        except Exception as e:
            logger.error(f"Failed to delete video metadata: {e}")
            raise
