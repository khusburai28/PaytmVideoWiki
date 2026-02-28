import logging
from typing import List, Dict
from datetime import datetime
import markdown
from weasyprint import HTML, CSS
from pathlib import Path

logger = logging.getLogger(__name__)


class ReportGenerator:
    def __init__(self, gemini_client):
        """Initialize report generator with Gemini client."""
        self.gemini_client = gemini_client

    def generate_report_content(
        self,
        video_name: str,
        description: str,
        duration: float,
        segments: List[Dict],
        additional_instructions: str = None
    ) -> str:
        """Generate structured markdown report using AI."""

        # Combine all transcript segments
        full_transcript = "\n\n".join([
            f"[{self._format_time(seg['start_time'])}] {seg['text']}"
            for seg in segments
        ])

        # Build the instruction section
        instruction_header = ""
        if additional_instructions:
            instruction_header = f"""

========================================
CRITICAL: USER'S ADDITIONAL INSTRUCTIONS
========================================

The user has explicitly provided the following ADDITIONAL INSTRUCTIONS that MUST take priority and be incorporated throughout the entire report:

--- START OF USER'S ADDITIONAL INSTRUCTIONS ---
{additional_instructions}
--- END OF USER'S ADDITIONAL INSTRUCTIONS ---

IMPORTANT: These are the user's specific requirements. They are MANDATORY and should significantly influence:
- The report's focus and emphasis
- The structure and organization
- The level of detail in relevant sections
- The technical depth and coverage

Ensure EVERY section of the report addresses these user instructions where applicable."""

        # Create AI prompt for report generation
        prompt = f"""You are a technical documentation expert. Generate a comprehensive, well-structured technical report based on the following video transcript.
{instruction_header}

Video Title: {video_name}
Description: {description}
Duration: {self._format_time(duration)}

TRANSCRIPT:
{full_transcript[:20000]}  # Limit to avoid token limits

"""

        additional_report_formatting_rule = f"""
Generate a professional technical report in Markdown format with the following structure:

# {video_name}

## Document Information
- **Date**: {datetime.now().strftime('%B %d, %Y')}
- **Duration**: {self._format_time(duration)}
- **Description**: {description}

## Executive Summary
[2-3 paragraph summary of the entire video content, highlighting the main objectives and key takeaways]

## Table of Contents
1. Agenda & Overview
2. Key Topics Covered
3. Technical Details
4. Important Concepts
5. Action Items & Next Steps
6. Q&A Summary (if applicable)
7. Resources & References

## 1. Agenda & Overview
[Detailed agenda of what was covered in the video]

## 2. Key Topics Covered
[List and explain each major topic discussed, with timestamps where relevant]

## 3. Technical Details
[Deep dive into technical concepts, architectures, code snippets mentioned, configurations, etc.]

## 4. Important Concepts
[Key concepts, definitions, best practices, and principles discussed]

## 5. Action Items & Next Steps
[Actionable items, follow-ups, things to implement, or next steps mentioned]

## 6. Q&A Summary
[If there were questions and answers, summarize them here]

## 7. Resources & References
[Any tools, libraries, documentation, or resources mentioned]

Important:
- Use proper Markdown formatting
- Include relevant timestamps using [MM:SS] format
- Be detailed and technical
- Organize information logically
- Use bullet points, numbered lists, and tables where appropriate
- Highlight code snippets with ```language``` blocks if code is mentioned
"""
        if not additional_instructions:
            prompt += additional_report_formatting_rule

        try:
            logger.info("Generating report content with AI...")
            report_markdown = self.gemini_client.generate_content(prompt)
            logger.info("Report content generated successfully")
            return report_markdown
        except Exception as e:
            logger.error(f"Failed to generate report content: {e}")
            raise

    def markdown_to_pdf(self, markdown_content: str, output_path: str):
        """Convert markdown to PDF with professional styling."""

        # Convert markdown to HTML
        html_content = markdown.markdown(
            markdown_content,
            extensions=['tables', 'fenced_code', 'codehilite', 'toc']
        )

        # Professional CSS styling for technical documentation
        css_content = """
        @page {
            size: A4;
            margin: 2cm;
            @top-right {
                content: counter(page);
                font-size: 10pt;
                color: #666;
            }
        }

        body {
            font-family: 'Helvetica', 'Arial', sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
        }

        h1 {
            color: #00BAF2;
            font-size: 28pt;
            font-weight: bold;
            margin-top: 0;
            margin-bottom: 10pt;
            border-bottom: 3px solid #00BAF2;
            padding-bottom: 10pt;
        }

        h2 {
            color: #002E5F;
            font-size: 20pt;
            font-weight: bold;
            margin-top: 20pt;
            margin-bottom: 10pt;
            border-bottom: 2px solid #E0E0E0;
            padding-bottom: 5pt;
            page-break-after: avoid;
        }

        h3 {
            color: #002E5F;
            font-size: 16pt;
            font-weight: bold;
            margin-top: 15pt;
            margin-bottom: 8pt;
            page-break-after: avoid;
        }

        h4 {
            color: #555;
            font-size: 13pt;
            font-weight: bold;
            margin-top: 12pt;
            margin-bottom: 6pt;
        }

        p {
            margin-bottom: 10pt;
            text-align: justify;
        }

        ul, ol {
            margin-bottom: 10pt;
            padding-left: 25pt;
        }

        li {
            margin-bottom: 5pt;
        }

        code {
            background-color: #f5f5f5;
            padding: 2pt 5pt;
            border-radius: 3pt;
            font-family: 'Courier New', monospace;
            font-size: 10pt;
            color: #d14;
        }

        pre {
            background-color: #f8f8f8;
            border: 1px solid #ddd;
            border-left: 3px solid #00BAF2;
            padding: 10pt;
            margin-bottom: 15pt;
            overflow-x: auto;
            page-break-inside: avoid;
        }

        pre code {
            background-color: transparent;
            padding: 0;
            color: #333;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15pt;
            page-break-inside: avoid;
        }

        th {
            background-color: #00BAF2;
            color: white;
            padding: 8pt;
            text-align: left;
            font-weight: bold;
        }

        td {
            padding: 8pt;
            border: 1px solid #ddd;
        }

        tr:nth-child(even) {
            background-color: #f9f9f9;
        }

        blockquote {
            border-left: 4px solid #00BAF2;
            padding-left: 15pt;
            margin-left: 0;
            color: #555;
            font-style: italic;
        }

        strong {
            color: #002E5F;
            font-weight: bold;
        }

        .timestamp {
            color: #00BAF2;
            font-weight: 600;
            font-family: monospace;
        }
        """

        # Wrap HTML with proper structure and embedded CSS
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Technical Documentation Report</title>
            <style>
            {css_content}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """

        try:
            logger.info(f"Converting markdown to PDF: {output_path}")
            # Create HTML object and write PDF
            HTML(string=full_html).write_pdf(output_path)
            logger.info("PDF generated successfully")
        except Exception as e:
            logger.error(f"Failed to convert markdown to PDF: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    async def generate_report(
        self,
        video_id: str,
        video_name: str,
        video_description: str,
        duration: float,
        segments: List[Dict],
        additional_instructions: str = None
    ) -> str:
        """Generate complete PDF report and return path."""
        # Generate markdown content
        markdown_content = self.generate_report_content(
            video_name=video_name,
            description=video_description,
            duration=duration,
            segments=segments,
            additional_instructions=additional_instructions
        )

        # Create output directory
        output_dir = Path("./temp")
        output_dir.mkdir(exist_ok=True)

        # Generate output path
        output_path = output_dir / f"{video_id}_report.pdf"

        # Convert to PDF
        self.markdown_to_pdf(markdown_content, str(output_path))

        return str(output_path)

    def _format_time(self, seconds: float) -> str:
        """Format seconds to HH:MM:SS or MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
