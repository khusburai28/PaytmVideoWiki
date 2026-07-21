from google import genai
from google.genai import types
from typing import List, Dict, Optional, Type
import logging
import fitz  # PyMuPDF

from app.utils.locators import format_locator

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
        """Generate response using Gemini with context retrieved from the document corpus."""

        # Build context from retrieved segments
        context_text = self._build_context(context_segments)

        # Log the context being used
        logger.info(f"Building prompt with {len(context_segments)} context segments")
        logger.debug(f"Context text preview: {context_text[:500]}...")

        # Build the system prompt with context
        system_prompt = f"""You are a concise industrial knowledge assistant. You answer questions using
evidence pulled from ingested plant documents (videos, PDFs, images, spreadsheets).

Guidelines:
- Format answers using bullet points for better readability
- Keep each bullet point clear and concise
- Each context item below is tagged with its source, e.g. "[Document Name — Page 4]" or "[Document Name — 12:34]" - you don't need to repeat these tags verbatim, just answer naturally
- Answer naturally as if you reviewed the source material yourself
- For simple questions, provide 2-3 key bullet points
- For detailed questions, organize information in logical bullet point sections
- Skip phrases like "based on the documents" - just answer directly
- Use sub-bullets for additional details when needed
- Use your own knowledge as well to answer the question

Source Content:
{context_text}
"""

        # Build the user query
        user_prompt = f"""Question: {query}

Answer concisely using the source content above. Keep it brief and natural."""

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
            logger.info("="*50)
            logger.info(f"[Gemini API Request] Full Prompt:\n{full_prompt}...")
            logger.info("="*50)

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=full_prompt
            )

            logger.info(f"[Gemini API Response] Status: Success | Response length: {len(response.text)} chars")
            logger.debug(f"[Gemini API Response] Full response:\n{response.text[:500]}...")

            return response.text

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise Exception(f"Failed to generate response: {str(e)}")

    def _build_context(self, segments: List[Dict]) -> str:
        """Build context string from chunk payloads, tagging each with its document name
        and a type-appropriate locator (timestamp, page number, or sheet/row range)."""
        context_parts = []
        for seg in segments:
            locator = format_locator(seg)
            doc_name = seg.get('document_name')
            tag = f"{doc_name} — {locator}" if doc_name else locator
            context_parts.append(f"[{tag}] {seg['text']}")

        return "\n".join(context_parts)

    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds to MM:SS or HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def generate_content(self, prompt: str) -> str:
        """Generate content using Gemini for report generation / summaries."""
        try:
            logger.info(f"[Gemini API - Content] Generating content with prompt length: {len(prompt)} chars")

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )

            logger.info(f"[Gemini API - Content] Response received: {len(response.text)} chars")
            return response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise Exception(f"Failed to generate content: {str(e)}")

    def generate_structured(self, prompt: str, response_schema: Type) -> str:
        """Generate content constrained to a JSON schema (a Pydantic model class) and
        return the raw JSON text. Used for entity/relationship extraction."""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema
                )
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini structured generation error: {e}")
            raise Exception(f"Failed structured generation: {str(e)}")

    def describe_image(self, image_bytes: bytes, instruction: str, mime_type: str = "image/png") -> str:
        """Send an image to Gemini vision and return the generated text. Used both for
        standalone image ingestion and for OCR-ing scanned/drawing-heavy PDF pages."""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[types.Part.from_bytes(data=image_bytes, mime_type=mime_type), instruction]
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini vision error: {e}")
            raise Exception(f"Failed to describe image: {str(e)}")

    def generate_response_with_files(
        self,
        query: str,
        context_segments: List[Dict],
        conversation_history: List[Dict] = None,
        files: List[Dict] = None
    ) -> str:
        """Generate response using Gemini with context and optional ad-hoc file uploads
        attached directly to this chat turn (these files are not indexed into the corpus)."""

        # If no files, use regular response generation
        if not files:
            return self.generate_response(query, context_segments, conversation_history)

        # Build context from retrieved chunks
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
                    content_parts.append(types.Part.from_bytes(data=content, mime_type=file_type))
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
        context_section = f"Source Content:\n{context_text}" if context_text else ""
        files_section = "Uploaded Files:\n" + "\n".join(file_descriptions) if file_descriptions else ""

        system_prompt = f"""You are an industrial knowledge assistant helping users understand ingested documents and analyze ad-hoc uploaded files.

Guidelines:
- Answer questions about both the source content and uploaded files
- Format answers using bullet points for clarity
- Reference specific parts of uploaded files when relevant
- Provide clear, concise responses

{context_section}

{files_section}
"""

        # Build user query
        user_prompt = f"Question: {query}\n\nPlease answer based on the source content and uploaded files."

        try:
            # Create content with both text and file parts
            contents = [types.Part(text=system_prompt)] + content_parts + [types.Part(text=user_prompt)]

            logger.info(f"[Gemini API - Files] Sending request with {len(files)} files and {len(content_parts)} content parts")

            # Generate response
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents
            )

            logger.info(f"[Gemini API - Files] Response received: {len(response.text)} chars")
            return response.text

        except Exception as e:
            logger.error(f"Gemini API error with files: {e}")
            raise Exception(f"Failed to generate response with files: {str(e)}")

    def _extract_pdf_text(self, pdf_content: bytes) -> str:
        """Extract text from PDF bytes (used for ad-hoc chat attachments)."""
        try:
            doc = fitz.open(stream=pdf_content, filetype="pdf")
            text_parts = [doc[i].get_text() for i in range(min(10, len(doc)))]
            doc.close()
            return "\n".join(text_parts)
        except Exception as e:
            logger.error(f"PDF extraction error: {e}")
            return ""

    def generate_diagram(self, query: str, segments: List[Dict]) -> str:
        """Generate a Mermaid diagram based on a document's content and a user query."""
        # Build context from chunk payloads
        context_text = self._build_context(segments[:50])  # Use first 50 chunks for context

        # Build the system prompt specifically for diagram generation
        system_prompt = f"""You are a diagram generation assistant. Your task is to create Mermaid diagrams based on document content.

CRITICAL REQUIREMENTS:
1. ONLY output valid Mermaid diagram syntax - NO explanations, NO markdown code blocks, NO additional text
2. Start directly with the diagram type (e.g., "graph TD", "flowchart LR", "sequenceDiagram", etc.)
3. Use proper Mermaid syntax - ensure all syntax is valid and follows Mermaid specification exactly
4. Keep diagrams clear and focused on 5-10 main concepts maximum
5. Use simple, alphanumeric node IDs (A, B, C or node1, node2, etc.)
6. DO NOT wrap the diagram in ```mermaid code blocks - output raw Mermaid syntax only
7. Test your syntax mentally before outputting - ensure it's valid Mermaid

Preferred diagram types (use these unless user requests specific type):
- flowchart TB (top to bottom flowchart - RECOMMENDED for most cases)
- graph LR (left to right graph)
- sequenceDiagram (for process flows with actors)

AVOID unless specifically requested:
- mindmap (often causes syntax errors)
- complex nested structures

Example of GOOD output:
flowchart TB
    A[Start] --> B[Check Condition]
    B -->|Yes| C[Process]
    B -->|No| D[End]
    C --> D

CRITICAL SYNTAX RULES - FOLLOW EXACTLY:
- ALWAYS use --> for connecting nodes (arrow with head)
- NEVER use -- or --- alone - these cause syntax errors
- For labels on arrows: -->|Label Text|
- Node shapes: ONLY use [square brackets] for labels - do NOT use (parentheses) in labels
- Keep node IDs simple: A, B, C or node1, node2
- Avoid special characters in labels: NO parentheses, NO curly braces, NO pipes
- Use simple alphanumeric text and spaces only in labels
- ALWAYS use [square brackets] for all node labels
- Each connection MUST have --> with an arrowhead
- Keep the diagram simple - max 10 nodes total
- For decision nodes, use text like "Is it X?" instead of shapes

Source Document Content:
{context_text}
"""

        # Build the user query
        user_prompt = f"""Based on the document content, create a FLOWCHART diagram that: {query}

IMPORTANT:
- Use "flowchart TB" or "flowchart LR" format ONLY
- DO NOT use mindmap, timeline, or other complex formats
- Output ONLY the Mermaid flowchart syntax
- No explanations, no markdown blocks, just the raw Mermaid code"""

        try:
            # Generate diagram using Gemini
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=f"{system_prompt}\n\n{user_prompt}"
            )

            diagram_code = response.text.strip()

            # Clean up the response - remove markdown code blocks if present
            if diagram_code.startswith("```mermaid"):
                diagram_code = diagram_code.replace("```mermaid", "").replace("```", "").strip()
            elif diagram_code.startswith("```"):
                diagram_code = diagram_code.replace("```", "").strip()

            # Fix common syntax errors
            # Replace --- with --> and -- with --> to fix connection syntax
            lines = diagram_code.split('\n')
            fixed_lines = []
            for line in lines:
                # Skip empty lines with just --
                if line.strip() == '--' or line.strip() == '---':
                    continue
                # Replace --- with -->
                line = line.replace(' --- ', ' --> ')
                # Replace standalone -- with -->
                line = line.replace(' -- ', ' --> ')

                # Remove parentheses from node labels to avoid syntax conflicts
                # Replace (text) with text in square bracket labels
                import re
                # Match patterns like [Text (Detail)] and replace with [Text - Detail]
                line = re.sub(r'\[([^\]]*)\(([^\)]+)\)([^\]]*)\]', r'[\1\2\3]', line)
                # Also handle the case where parentheses might remain
                line = line.replace('(', '').replace(')', '')

                fixed_lines.append(line)

            diagram_code = '\n'.join(fixed_lines)

            # Log the full diagram for debugging
            logger.info(f"Generated Mermaid diagram:\n{diagram_code}")
            return diagram_code

        except Exception as e:
            logger.error(f"Diagram generation error: {e}")
            raise Exception(f"Failed to generate diagram: {str(e)}")
