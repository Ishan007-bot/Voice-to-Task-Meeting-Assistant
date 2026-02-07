"""
Tests for Meetings API
"""

import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock


class TestMeetingsAPI:
    """Test suite for meetings endpoints."""
    
    @pytest.mark.asyncio
    async def test_create_meeting(self, authenticated_client: AsyncClient):
        """Test creating a new meeting."""
        response = await authenticated_client.post(
            "/api/v1/meetings",
            json={
                "title": "Team Standup",
                "description": "Daily standup meeting",
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Team Standup"
        assert data["status"] == "pending"
        assert "id" in data
    
    @pytest.mark.asyncio
    async def test_list_meetings(self, authenticated_client: AsyncClient):
        """Test listing meetings."""
        # Create a meeting first
        await authenticated_client.post(
            "/api/v1/meetings",
            json={"title": "Test Meeting"},
        )
        
        response = await authenticated_client.get("/api/v1/meetings")
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) >= 1
    
    @pytest.mark.asyncio
    async def test_get_meeting(self, authenticated_client: AsyncClient):
        """Test getting a specific meeting."""
        # Create a meeting
        create_response = await authenticated_client.post(
            "/api/v1/meetings",
            json={"title": "Get Test Meeting"},
        )
        meeting_id = create_response.json()["id"]
        
        # Get the meeting
        response = await authenticated_client.get(f"/api/v1/meetings/{meeting_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == meeting_id
        assert data["title"] == "Get Test Meeting"
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_meeting(self, authenticated_client: AsyncClient):
        """Test getting a non-existent meeting returns 404."""
        response = await authenticated_client.get(
            "/api/v1/meetings/00000000-0000-0000-0000-000000000000"
        )
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_update_meeting(self, authenticated_client: AsyncClient):
        """Test updating a meeting."""
        # Create a meeting
        create_response = await authenticated_client.post(
            "/api/v1/meetings",
            json={"title": "Original Title"},
        )
        meeting_id = create_response.json()["id"]
        
        # Update the meeting
        response = await authenticated_client.patch(
            f"/api/v1/meetings/{meeting_id}",
            json={"title": "Updated Title", "description": "Added description"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["description"] == "Added description"
    
    @pytest.mark.asyncio
    async def test_delete_meeting(self, authenticated_client: AsyncClient):
        """Test deleting a meeting."""
        # Create a meeting
        create_response = await authenticated_client.post(
            "/api/v1/meetings",
            json={"title": "To Delete"},
        )
        meeting_id = create_response.json()["id"]
        
        # Delete the meeting
        response = await authenticated_client.delete(f"/api/v1/meetings/{meeting_id}")
        
        assert response.status_code == 204
        
        # Verify it's deleted
        get_response = await authenticated_client.get(f"/api/v1/meetings/{meeting_id}")
        assert get_response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_meeting_status(self, authenticated_client: AsyncClient):
        """Test getting meeting processing status."""
        # Create a meeting
        create_response = await authenticated_client.post(
            "/api/v1/meetings",
            json={"title": "Status Test"},
        )
        meeting_id = create_response.json()["id"]
        
        # Get status
        response = await authenticated_client.get(f"/api/v1/meetings/{meeting_id}/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["meeting_id"] == meeting_id
        assert "status" in data
        assert "progress" in data
