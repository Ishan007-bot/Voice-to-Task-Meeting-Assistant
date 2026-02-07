"""
API Router Configuration
Combines all API route modules.
"""

from fastapi import APIRouter

from app.api.routes import auth, meetings, tasks, transcripts, integrations, health

api_router = APIRouter()

# Include all route modules
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(meetings.router, prefix="/meetings", tags=["Meetings"])
api_router.include_router(transcripts.router, prefix="/transcripts", tags=["Transcripts"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
api_router.include_router(integrations.router, prefix="/integrations", tags=["Integrations"])
