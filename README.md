# Video RAG System

A secure, local video RAG (Retrieval-Augmented Generation) system that allows you to chat with your videos, get AI-powered answers with precise timestamps, and navigate directly to relevant video segments.

## Features

- Upload and process videos locally (keeps your confidential data secure)
- Automatic transcription with timestamps using Whisper
- AI-powered chat interface with follow-up questions
- Clickable timestamps that jump to exact video moments
- Vector search using Qdrant for accurate context retrieval
- Powered by Google Gemini API for intelligent responses

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: React + Vite
- **Vector Database**: Qdrant (self-hosted)
- **LLM**: Google Gemini API
- **Transcription**: OpenAI Whisper
- **Video Processing**: ffmpeg
- **Deployment**: Docker Compose

## Prerequisites

- Docker and Docker Compose
- Google Gemini API key ([Get it here](https://aistudio.google.com/app/api-keys))
- At least 4GB RAM for video processing

## Quick Start

1. **Clone and setup**
   ```bash
   cd VideoRAG
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and add your GEMINI_API_KEY
   ```

3. **Start the application**
   ```bash
   docker-compose up -d
   ```

4. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs


## Default Admin Account:

- Email: admin@example.com
- Password: Admin@123456

## Usage

1. **Upload Video**: Click "Upload Video" and select your MP4/MOV/AVI file
2. **Wait for Processing**: The system will transcribe and index your video (takes 2-5 minutes)
3. **Start Chatting**: Ask questions about the video content
4. **Click Timestamps**: Click any timestamp in the chat to jump to that moment in the video

## Security & Privacy

- All video processing happens locally
- Videos never leave your infrastructure
- Qdrant vector database runs locally
- Only chat queries and transcription text are sent to Gemini API (not the video itself)
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

## If any changes are made then we can rebuild using

```
# If changes made to frontend
docker-compose up -d --build frontend

# If changes made to backend
docker-compose up -d --build backend
```

## Configuration

Edit `.env` file:

```env
# Gemini API
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-3.1-pro-preview

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Upload settings
MAX_VIDEO_SIZE_MB=500
UPLOAD_DIR=./uploads
```
