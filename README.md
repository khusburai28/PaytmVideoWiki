# KnowForge AI — Industrial Knowledge Intelligence Platform

Ingests videos, PDFs, images, and spreadsheets into one unified, queryable knowledge base — with a real extracted knowledge graph and a corpus-wide RAG copilot with citations. Built to address knowledge fragmentation in asset-intensive industrial operations: maintenance records, inspection reports, safety procedures, and drawings scattered across disconnected systems, made queryable from one place.

## 🎥 Demo

Watch the complete application walkthrough here :

**YouTube :** https://youtu.be/Gchm8ro0RpA?si=pkf9Ix6c4CVP9x3_

## Application Preview

<img width="1287" height="727" alt="Screenshot 2026-07-23 at 4 03 21 PM" src="https://github.com/user-attachments/assets/679f0e90-dc66-484e-a678-c2a0cc82f850" />
<img width="1296" height="728" alt="Screenshot 2026-07-23 at 4 02 12 PM" src="https://github.com/user-attachments/assets/a1c41e2b-1e31-45ec-a361-607847304e41" />
<img width="1294" height="726" alt="Screenshot 2026-07-23 at 4 02 40 PM" src="https://github.com/user-attachments/assets/ace9a817-bed2-44e9-889d-18a6ccb459d2" />



## Features

- **Multi-format ingestion** — video (Whisper transcription), PDF (page-level text extraction with Gemini-vision OCR fallback for scanned pages), images (Gemini-vision description/OCR), spreadsheets (XLSX/XLS/CSV with per-sheet and per-row-group chunking)
- **Knowledge graph** — entities (equipment, personnel, dates, regulations, process parameters, locations, organizations, incidents, work orders) and relationships extracted via Gemini structured output, persisted with networkx. The same equipment tag mentioned across a PDF, spreadsheet, and image collapses into one shared node — proving the knowledge is actually unified, not just co-located
- **Corpus-wide copilot** — ask a question scoped to one document, or across your whole team's knowledge base, with structured source citations (timestamp / page number / sheet+row range, depending on document type)
- **Document viewers** — video player, native PDF viewer with page deep-linking, image viewer, spreadsheet row preview
- **Evidence packs & diagrams** — generate a PDF evidence-pack report or an ad-hoc Mermaid flow diagram for any document
- **Team-based auth** — admin / team lead / employee roles, with team-scoped visibility

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: React + Vite
- **Vector Database**: Qdrant (self-hosted; also used as the app's document/user/team datastore)
- **LLM, embeddings & vision**: Google Gemini API
- **Knowledge graph**: networkx, persisted as JSON (no separate graph database)
- **Video transcription**: OpenAI Whisper + ffmpeg
- **PDF parsing**: PyMuPDF
- **Spreadsheet parsing**: pandas / openpyxl
- **Graph visualization**: react-force-graph-2d
- **Deployment**: Docker Compose

## Prerequisites

- Docker and Docker Compose
- Google Gemini API key ([get one here](https://aistudio.google.com/app/api-keys)) — note the free tier caps `gemini-2.5-flash` at roughly 20 requests/day; use a paid tier for real testing or a demo, since ingestion, chat, and entity extraction all consume this quota
- At least 4GB RAM for video processing

## Quick Start

1. **Configure environment**
   ```bash
   cp .env.example .env
   # edit .env and add your GEMINI_API_KEY
   ```

2. **Start the application**
   ```bash
   docker-compose up -d
   ```

3. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

## Default Admin Account

- Email: `admin@example.com`
- Password: `Admin@123456`

## Usage

1. **Ingest**: click "Ingest & Index" and drop a video, PDF, image, or spreadsheet — or use the ready-made files in [`sample_data/`](sample_data/README.md)
2. **Wait for processing**: video transcription takes the longest (minutes); PDFs, images, and spreadsheets typically finish in seconds
3. **Explore**:
   - **Records** — browse and search your document library, view or play each document, generate an evidence-pack report or a quick flow diagram
   - **Copilot** — ask questions scoped to one open document, or use the top-nav Copilot for corpus-wide search across everything your team has ingested
   - **Knowledge Graph** — see extracted entities and relationships across your whole corpus; click a node to see which documents mention it

## Sample Documents

[`sample_data/`](sample_data/README.md) contains synthetic industrial documents — two PDFs, a multi-sheet work-order spreadsheet, and two images — that deliberately reuse the same equipment tags across formats, so you can watch the knowledge graph cross-link them after ingestion.

## Security & Privacy

- All processing happens in your own Docker environment
- Only extracted text/embeddings and chat queries are sent to the Gemini API — original files stay on your infrastructure
- Add network isolation in production

## Development

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Rebuilding after changes

```bash
# If changes made to frontend
docker-compose up -d --build frontend

# If changes made to backend
docker-compose up -d --build backend
```

## Configuration

Edit `.env`:

```env
# Gemini API
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# Qdrant
QDRANT_HOST=qdrant
QDRANT_PORT=6333
QDRANT_COLLECTION=document_chunks
QDRANT_METADATA_COLLECTION=document_metadata

# Application settings
MAX_VIDEO_SIZE_MB=5120
UPLOAD_DIR=./uploads
TEMP_DIR=./temp
DATA_DIR=./data

# Embedding model (Gemini)
EMBEDDING_MODEL=gemini-embedding-001

# Whisper settings
WHISPER_MODEL=base
# Options: tiny, base, small, medium, large — larger = more accurate but slower
```

## Roadmap

Not yet built, but the data model leaves room for both without further schema changes:
- **Maintenance Intelligence & RCA Agent** — the knowledge graph already models `incident` and `work_order` entity types
- **Quality & Regulatory Compliance Intelligence** — the graph already models `regulation` entities and links them to equipment
