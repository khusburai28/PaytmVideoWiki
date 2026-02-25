#!/bin/bash

# Video RAG Quick Start Script

set -e

echo "========================================="
echo "Video RAG System - Quick Start"
echo "========================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running!"
    echo "Please start Docker Desktop and try again."
    exit 1
fi

echo "✅ Docker is running"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found!"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo ""
    echo "📝 Please edit .env file and add your GEMINI_API_KEY"
    echo "   Get your key from: https://makersuite.google.com/app/apikey"
    echo ""
    echo "   nano .env   (or use any text editor)"
    echo ""
    echo "After adding your API key, run this script again:"
    echo "   ./start.sh"
    exit 0
fi

# Check if GEMINI_API_KEY is set
source .env
if [ -z "$GEMINI_API_KEY" ] || [ "$GEMINI_API_KEY" = "your_gemini_api_key_here" ]; then
    echo "❌ Error: GEMINI_API_KEY not set in .env file"
    echo ""
    echo "Please edit .env and add your Gemini API key:"
    echo "   Get your key from: https://makersuite.google.com/app/apikey"
    echo ""
    echo "   nano .env   (or use any text editor)"
    exit 1
fi

echo "✅ Environment configured"
echo ""

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p uploads temp qdrant_data
echo "✅ Directories created"
echo ""

# Check if containers are already running
if docker-compose ps | grep -q "Up"; then
    echo "⚠️  Containers are already running"
    echo ""
    echo "Options:"
    echo "  1. Stop and restart:  docker-compose restart"
    echo "  2. View logs:         docker-compose logs -f"
    echo "  3. Stop:              docker-compose down"
    echo ""
    echo "Access the application at: http://localhost:3000"
    exit 0
fi

# Start Docker Compose
echo "🚀 Starting Video RAG system..."
echo ""
echo "This will:"
echo "  - Download Docker images (first time only)"
echo "  - Start Qdrant vector database"
echo "  - Start FastAPI backend"
echo "  - Start React frontend"
echo ""

docker-compose up -d

# Wait for services to be ready
echo ""
echo "⏳ Waiting for services to start..."
sleep 5

# Check if services are running
if docker-compose ps | grep -q "Up"; then
    echo ""
    echo "========================================="
    echo "✅ Video RAG system is running!"
    echo "========================================="
    echo ""
    echo "🌐 Access points:"
    echo "   Frontend:       http://localhost:3000"
    echo "   API Docs:       http://localhost:8000/docs"
    echo "   Qdrant:         http://localhost:6333/dashboard"
    echo ""
    echo "📖 Quick tips:"
    echo "   - Upload a video and wait 2-5 minutes for processing"
    echo "   - Ask questions about the video content"
    echo "   - Click timestamps to jump to relevant moments"
    echo ""
    echo "🛠️  Useful commands:"
    echo "   View logs:      docker-compose logs -f"
    echo "   Stop system:    docker-compose down"
    echo "   Restart:        docker-compose restart"
    echo ""
    echo "📚 Documentation:"
    echo "   README.md       - Overview and features"
    echo "   SETUP.md        - Detailed setup guide"
    echo "   ARCHITECTURE.md - Technical architecture"
    echo ""
else
    echo ""
    echo "❌ Error: Services failed to start"
    echo ""
    echo "Check logs with: docker-compose logs"
    exit 1
fi
