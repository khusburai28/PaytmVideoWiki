from google import genai
from google.genai import types
from typing import List, Dict, Optional
import logging
import base64
from PIL import Image
import io
import PyPDF2

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
- Format answers using bullet points for better readability
- Keep each bullet point clear and concise
- Use timestamps MM:SS or HH:MM:SS when referencing specific moments (DO NOT use square brackets around timestamps)
- Answer naturally as if you watched the video
- For simple questions, provide 2-3 key bullet points
- For detailed questions, organize information in logical bullet point sections
- Skip phrases like "based on the transcript" - just answer directly
- Use sub-bullets for additional details when needed
- Use your own knowledge as well to answer the question

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

    def generate_content(self, prompt: str) -> str:
        """Generate content using Gemini for report generation."""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise Exception(f"Failed to generate content: {str(e)}")

    def generate_response_with_files(
        self,
        query: str,
        context_segments: List[Dict],
        conversation_history: List[Dict] = None,
        files: List[Dict] = None
    ) -> str:
        """Generate response using Gemini with context and optional file uploads."""

        # If no files, use regular response generation
        if not files:
            return self.generate_response(query, context_segments, conversation_history)

        # Build context from video segments
        context_text = self._build_context(context_segments) if context_segments else ""

        # Process files and create content parts
        content_parts = []
        file_descriptions = []

        for file_info in files:
            file_type = file_info['content_type']
            content = file_info['content']
            filename = file_info['filename']

            try:
                if file_type.startswith('image/'):
                    # Handle image files
                    image = Image.open(io.BytesIO(content))
                    content_parts.append(types.Part.from_image(image=image))
                    file_descriptions.append(f"- Image: {filename}")
                    logger.info(f"Processed image: {filename}")

                elif file_type == 'application/pdf':
                    # Extract text from PDF
                    pdf_text = self._extract_pdf_text(content)
                    if pdf_text:
                        content_parts.append(types.Part(text=f"PDF Content from {filename}:\n{pdf_text[:5000]}"))  # Limit PDF text
                        file_descriptions.append(f"- PDF: {filename}")
                        logger.info(f"Processed PDF: {filename}")

                elif file_type.startswith('text/') or filename.endswith(('.txt', '.md', '.doc', '.docx')):
                    # Handle text files
                    try:
                        text_content = content.decode('utf-8')
                        content_parts.append(types.Part(text=f"File content from {filename}:\n{text_content[:5000]}"))
                        file_descriptions.append(f"- Text file: {filename}")
                        logger.info(f"Processed text file: {filename}")
                    except:
                        file_descriptions.append(f"- File (could not read): {filename}")

            except Exception as e:
                logger.error(f"Error processing file {filename}: {e}")
                file_descriptions.append(f"- File (error processing): {filename}")

        # Build the system prompt
        video_section = f"Video Content:\n{context_text}" if context_text else ""
        files_section = "Uploaded Files:\n" + "\n".join(file_descriptions) if file_descriptions else ""

        system_prompt = f"""You are a knowledge transfer assistant helping users understand video content and analyze uploaded files.

Guidelines:
- Answer questions about both the video content and uploaded files
- Format answers using bullet points for clarity
- Use timestamps MM:SS or HH:MM:SS when referencing video moments (DO NOT use square brackets around timestamps)
- Reference specific parts of uploaded files when relevant
- Provide clear, concise responses

{video_section}

{files_section}
"""

        # Build user query
        user_prompt = f"Question: {query}\n\nPlease answer based on the video content and uploaded files."

        try:
            # Create content with both text and file parts
            contents = [types.Part(text=system_prompt)] + content_parts + [types.Part(text=user_prompt)]

            # Generate response
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents
            )
            return response.text

        except Exception as e:
            logger.error(f"Gemini API error with files: {e}")
            raise Exception(f"Failed to generate response with files: {str(e)}")

    def _extract_pdf_text(self, pdf_content: bytes) -> str:
        """Extract text from PDF bytes."""
        try:
            pdf_file = io.BytesIO(pdf_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text_parts = []

            # Extract text from first 10 pages
            for page_num in range(min(10, len(pdf_reader.pages))):
                page = pdf_reader.pages[page_num]
                text_parts.append(page.extract_text())

            return "\n".join(text_parts)
        except Exception as e:
            logger.error(f"PDF extraction error: {e}")
            return ""
