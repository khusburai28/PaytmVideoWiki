from google import genai
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class GeminiClient:
    def __init__(self, api_key: str, model_name: str = "gemini-1.5-pro"):
        """Initialize Gemini API client."""
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.chat_sessions: Dict[str, any] = {}
        logger.info(f"Gemini client initialized with model: {model_name}")

    def generate_response(
        self,
        query: str,
        context_segments: List[Dict],
        conversation_history: List[Dict] = None
    ) -> str:
        """Generate response using Gemini with context from video transcripts."""

        # Build context from retrieved segments
        context_text = self._build_context(context_segments)

        # Build the prompt
        system_prompt = """You are a helpful AI assistant that answers questions about video content.
You have access to transcribed segments from a video with their timestamps.

Instructions:
- Answer questions based ONLY on the provided transcript segments
- When referencing specific moments, mention the timestamp naturally in your response
- If the answer is not in the provided context, say so honestly
- Be conversational and helpful
- If asked for follow-up questions, use the conversation history to maintain context
"""

        user_prompt = f"""Video Transcript Context:
{context_text}

Question: {query}

Please provide a detailed answer based on the video transcript above. Include relevant timestamps when referencing specific parts."""

        try:
            # Include conversation history if available
            full_prompt = system_prompt + "\n\n" + user_prompt

            if conversation_history:
                history_text = "\n".join([
                    f"{msg['role'].capitalize()}: {msg['content']}"
                    for msg in conversation_history[-6:]  # Last 3 exchanges
                ])
                full_prompt = f"{system_prompt}\n\nConversation History:\n{history_text}\n\n{user_prompt}"

            # Generate response using new API
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=full_prompt
            )
            return response.text

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise Exception(f"Failed to generate response: {str(e)}")

    def _build_context(self, segments: List[Dict]) -> str:
        """Build context string from transcript segments."""
        context_parts = []
        for seg in segments:
            timestamp = self._format_timestamp(seg['start_time'])
            text = seg['text']
            context_parts.append(f"[{timestamp}] {text}")

        return "\n".join(context_parts)

    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds to MM:SS or HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def extract_timestamps_from_response(self, response_text: str, all_segments: List[Dict]) -> List[Dict]:
        """
        Extract timestamp references from the AI response.
        This is a simple implementation - matches timestamps mentioned in the response
        with the original segments.
        """
        referenced_segments = []

        # Simple approach: return the segments that were used in context
        # In a more advanced implementation, you could parse the response for specific timestamp mentions
        for seg in all_segments:
            referenced_segments.append({
                "start_time": seg['start_time'],
                "end_time": seg['end_time'],
                "text": seg['text'][:100] + "..." if len(seg['text']) > 100 else seg['text'],
                "relevance_score": seg.get('score', 0.8)
            })

        return referenced_segments[:3]  # Return top 3 most relevant
