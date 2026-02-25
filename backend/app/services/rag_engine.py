from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from google import genai
from typing import List, Dict
import logging
import uuid

logger = logging.getLogger(__name__)


class RAGEngine:
    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        collection_name: str = "video_transcripts",
        gemini_api_key: str = None,
        embedding_model: str = "gemini-embedding-004"
    ):
        """Initialize RAG engine with Qdrant and Gemini embedding model."""
        self.collection_name = collection_name
        self.embedding_model_name = embedding_model

        # Initialize Qdrant client
        logger.info(f"Connecting to Qdrant at {qdrant_host}:{qdrant_port}")
        self.qdrant_client = QdrantClient(host=qdrant_host, port=qdrant_port)

        # Initialize Gemini client for embeddings
        logger.info(f"Initializing Gemini embedding model: {embedding_model}")
        self.genai_client = genai.Client(api_key=gemini_api_key)

        # Gemini embedding dimension is 768 for gemini-embedding-004
        self.embedding_dim = 768

        # Create collection if it doesn't exist
        self._ensure_collection_exists()

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

    def index_video_segments(self, video_id: str, segments: List[Dict]):
        """Index video transcript segments into Qdrant."""
        try:
            logger.info(f"Indexing {len(segments)} segments for video {video_id}")

            # Prepare points for insertion
            points = []
            for idx, segment in enumerate(segments):
                # Generate embedding for the text using Gemini
                embedding = self._generate_embedding(segment['text'])

                # Create point with metadata
                point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload={
                        "video_id": video_id,
                        "text": segment['text'],
                        "start_time": segment['start_time'],
                        "end_time": segment['end_time'],
                        "confidence": segment.get('confidence', 0.0),
                        "segment_index": idx
                    }
                )
                points.append(point)

            # Upload points in batches
            batch_size = 100
            for i in range(0, len(points), batch_size):
                batch = points[i:i + batch_size]
                self.qdrant_client.upsert(
                    collection_name=self.collection_name,
                    points=batch
                )

            logger.info(f"Successfully indexed {len(segments)} segments for video {video_id}")

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
