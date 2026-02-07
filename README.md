# 🎙️ Voice-to-Task Meeting Assistant

<div align="center">

![Voice-to-Task](https://img.shields.io/badge/Voice--to--Task-Meeting%20Assistant-27ab83?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?style=flat-square&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18.2-61DAFB?style=flat-square&logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white)

**Transform your meetings into actionable tasks with AI-powered transcription and task extraction.**

[Features](#-features) • [Quick Start](#-quick-start) • [Architecture](#-architecture) • [API Docs](#-api-documentation) • [Contributing](#-contributing)

</div>

---

## ✨ Features

### 🎤 Audio Processing
- **Record or Upload** - Capture meetings directly or upload audio files (WAV, MP3, M4A, OGG, FLAC)
- **Large File Support** - Handle recordings up to 500MB with streaming uploads
- **Audio Normalization** - Automatic format conversion for optimal transcription

### 🗣️ Transcription
- **OpenAI Whisper** - High-accuracy speech-to-text (local or API)
- **Chunked Processing** - Handle long meetings (20+ minutes) without memory issues
- **Speaker Diarization** - Identify different speakers ("Speaker 1", "Speaker 2")

### 🧠 AI Task Extraction
- **GPT-4o Powered** - Intelligent extraction of action items from transcripts
- **Structured Output** - Reliable JSON responses with LangChain
- **Smart Prioritization** - Automatic priority assignment based on context

### 🔗 Integrations
- **Asana** - Sync tasks to your Asana projects
- **Trello** - Create cards in your Trello boards
- **Extensible** - Adapter pattern for easy addition of new services

### 🔒 Security
- **JWT Authentication** - Secure token-based auth
- **PII Redaction** - Automatic masking of sensitive data
- **Rate Limiting** - Protection against abuse

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- OpenAI API Key
- (Optional) Asana/Trello API keys for integrations

### 1. Clone the Repository

```bash
git clone https://github.com/Ishan007-bot/Voice-to-Task-Meeting-Assistant.git
cd Voice-to-Task-Meeting-Assistant
```

### 2. Configure Environment

```bash
# Copy the example environment file
cp env.example .env

# Edit .env with your API keys
nano .env  # or use your preferred editor
```

**Required environment variables:**
```env
OPENAI_API_KEY=sk-your-openai-api-key
JWT_SECRET_KEY=your-secure-random-string
SECRET_KEY=your-app-secret-key
```

### 3. Start with Docker

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Check status
docker-compose ps
```

### 4. Access the Application

| Service | URL |
|---------|-----|
| **Frontend** | http://localhost:3000 |
| **Backend API** | http://localhost:8000 |
| **API Docs** | http://localhost:8000/docs |
| **Flower (Celery)** | http://localhost:5555 |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         React Frontend                          │
│                    (Vite + Tailwind CSS)                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Auth API  │  │ Meeting API │  │    WebSocket Server     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌───────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  PostgreSQL   │  │     Redis       │  │  Celery Worker  │
│  + pgvector   │  │  (Task Queue)   │  │                 │
└───────────────┘  └─────────────────┘  └────────┬────────┘
                                                 │
                   ┌─────────────────────────────┼─────────────────┐
                   ▼                             ▼                 ▼
            ┌─────────────┐            ┌─────────────┐    ┌─────────────┐
            │   Whisper   │            │   GPT-4o    │    │  Asana/     │
            │ (Transcribe)│            │ (Extract)   │    │  Trello     │
            └─────────────┘            └─────────────┘    └─────────────┘
```

---

## 📁 Project Structure

```
├── app/
│   ├── api/                 # FastAPI routes
│   │   └── routes/          # Endpoint modules
│   ├── core/                # Config, security, logging
│   ├── db/                  # Database session & models
│   ├── models/              # SQLAlchemy models
│   ├── repositories/        # Data access layer
│   ├── schemas/             # Pydantic schemas
│   ├── services/            # Business logic
│   │   ├── audio.py         # Audio processing
│   │   ├── transcription.py # Whisper integration
│   │   ├── task_extraction.py # LangChain + GPT-4o
│   │   └── pii_redaction.py # PII masking
│   ├── integrations/        # External service adapters
│   ├── workers/             # Celery tasks
│   └── websocket/           # Real-time updates
├── tests/                   # Pytest test suite
├── alembic/                 # Database migrations
├── frontend/                # React application (separate repo)
├── docker-compose.yml       # Docker orchestration
├── Dockerfile               # Backend container
└── requirements.txt         # Python dependencies
```

---

## 📖 API Documentation

### Authentication

```bash
# Register
POST /api/v1/auth/register
{
  "email": "user@example.com",
  "password": "SecurePass123",
  "full_name": "John Doe"
}

# Login
POST /api/v1/auth/login
{
  "email": "user@example.com",
  "password": "SecurePass123"
}
# Returns: { access_token, refresh_token }
```

### Meetings

```bash
# Create meeting
POST /api/v1/meetings
{ "title": "Team Standup" }

# Upload audio
POST /api/v1/meetings/{id}/upload
Content-Type: multipart/form-data
file: <audio-file>

# Get meeting status
GET /api/v1/meetings/{id}/status
```

### Tasks

```bash
# List tasks for meeting
GET /api/v1/tasks/meeting/{meeting_id}

# Update task
PATCH /api/v1/tasks/{id}
{ "status": "pending", "priority": "high" }

# Sync to external service
POST /api/v1/tasks/sync
{ "task_ids": ["..."], "integration_id": "..." }
```

Full API documentation available at `/docs` when running the server.

---

## 🧪 Running Tests

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run specific test file
pytest tests/test_task_extraction.py -v
```

---

## 🔧 Development Setup

### Without Docker

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start PostgreSQL and Redis (install separately)

# 4. Run database migrations
alembic upgrade head

# 5. Start the API server
uvicorn app.main:app --reload

# 6. Start Celery worker (separate terminal)
celery -A app.workers.celery_app worker --loglevel=info
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## 🌐 Deployment

### Docker Compose (Recommended)

```bash
# Production build
docker-compose -f docker-compose.yml up -d --build
```

### Environment Variables

See `env.example` for all configuration options.

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key for GPT-4o and Whisper | ✅ |
| `DATABASE_URL` | PostgreSQL connection string | ✅ |
| `REDIS_URL` | Redis connection string | ✅ |
| `JWT_SECRET_KEY` | Secret for JWT tokens | ✅ |
| `ASANA_PERSONAL_ACCESS_TOKEN` | Asana integration | ❌ |
| `TRELLO_API_KEY` | Trello integration | ❌ |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [OpenAI Whisper](https://github.com/openai/whisper) - Speech recognition
- [LangChain](https://langchain.com/) - LLM orchestration
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [pgvector](https://github.com/pgvector/pgvector) - Vector similarity search

---

<div align="center">

**Built with ❤️ for productive meetings**

[⬆ Back to Top](#️-voice-to-task-meeting-assistant)

</div>
