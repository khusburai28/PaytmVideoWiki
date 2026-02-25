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

        # Log the context being used
        logger.info(f"Building prompt with {len(context_segments)} context segments")
        logger.debug(f"Context text preview: {context_text[:500]}...")

        # Build the system prompt with context
        system_prompt = f"""You are a concise knowledge transfer assistant for developer training videos.

Guidelines:
- Keep answers SHORT and to-the-point (2-3 sentences max for simple questions)
- Answer naturally as if you watched the video
- Use timestamps [MM:SS] when referencing specific moments
- Don't repeat information or over-explain
- If asked "what is this about", give a ONE sentence summary
- For detailed questions, provide focused details only
- Skip phrases like "based on the transcript" - just answer directly

Video Content:
{context_text}
"""

        # Build the user query
        user_prompt = f"""Question: {query}

Answer concisely using the video content. Keep it brief and natural."""

        try:
            # Build full prompt with conversation history if available
            if conversation_history and len(conversation_history) > 0:
                history_text = "\n".join([
                    f"{msg['role'].capitalize()}: {msg['content']}"
                    for msg in conversation_history[-6:]  # Last 3 exchanges
                ])
                full_prompt = f"{system_prompt}\n\nPrevious Conversation:\n{history_text}\n\n{user_prompt}"
            else:
                full_prompt = f"{system_prompt}\n\n{user_prompt}"

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
