"""
Tests for Task Extraction Service
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.task_extraction import TaskExtractionService, TaskListSchema, TaskSchema
from app.schemas.task import ExtractedTask


class TestTaskExtractionService:
    """Test suite for TaskExtractionService."""
    
    @pytest.fixture
    def service(self):
        """Create a TaskExtractionService instance."""
        return TaskExtractionService()
    
    @pytest.mark.asyncio
    async def test_extract_tasks_from_transcript(self, service):
        """Test basic task extraction from a transcript."""
        transcript = """
        John: Alright team, let's wrap up. Sarah, can you update the documentation 
        by Friday? It's really important.
        
        Sarah: Sure, I'll get that done.
        
        John: Great. Mike, please review the security audit results when you have time.
        
        Mike: Will do, probably next week.
        
        John: Also, we need to fix the login bug before the release. That's high priority.
        """
        
        # Mock the LLM response
        mock_result = TaskListSchema(
            tasks=[
                TaskSchema(
                    title="Update documentation",
                    description="Sarah needs to update the documentation",
                    priority="High",
                    assignee="Sarah",
                    due_date="2024-01-12",  # Friday
                ),
                TaskSchema(
                    title="Review security audit results",
                    description="Mike to review security audit results",
                    priority="Low",
                    assignee="Mike",
                    due_date="TBD",
                ),
                TaskSchema(
                    title="Fix login bug",
                    description="Fix the login bug before release",
                    priority="High",
                    assignee="Unassigned",
                    due_date="TBD",
                ),
            ]
        )
        
        with patch.object(service, 'structured_llm') as mock_llm:
            # Create a mock chain
            mock_chain = MagicMock()
            mock_chain.ainvoke = AsyncMock(return_value=mock_result)
            
            with patch.object(service, 'prompt') as mock_prompt:
                mock_prompt.__or__ = MagicMock(return_value=mock_chain)
                
                tasks = await service.extract_tasks(transcript)
        
                assert len(tasks) == 3
                assert tasks[0].title == "Update documentation"
                assert tasks[0].assignee == "Sarah"
                assert tasks[2].priority == "High"
    
    @pytest.mark.asyncio
    async def test_extract_tasks_empty_transcript(self, service):
        """Test that empty/short transcripts return empty list."""
        transcript = "Hi"
        
        tasks = await service.extract_tasks(transcript)
        
        assert tasks == []
    
    def test_normalize_priority_high(self, service):
        """Test priority normalization for high priority."""
        assert service._normalize_priority("high") == "High"
        assert service._normalize_priority("URGENT") == "High"
        assert service._normalize_priority("critical") == "High"
    
    def test_normalize_priority_low(self, service):
        """Test priority normalization for low priority."""
        assert service._normalize_priority("low") == "Low"
        assert service._normalize_priority("minor") == "Low"
    
    def test_normalize_priority_medium(self, service):
        """Test priority normalization defaults to medium."""
        assert service._normalize_priority("medium") == "Medium"
        assert service._normalize_priority("normal") == "Medium"
        assert service._normalize_priority("unknown") == "Medium"
    
    def test_parse_due_date_iso_format(self, service):
        """Test parsing ISO format dates."""
        from datetime import date
        
        result = service.parse_due_date("2024-01-15")
        assert result == date(2024, 1, 15)
    
    def test_parse_due_date_tbd(self, service):
        """Test that TBD returns None."""
        assert service.parse_due_date("TBD") is None
        assert service.parse_due_date("tbd") is None
        assert service.parse_due_date("") is None
        assert service.parse_due_date(None) is None
    
    def test_map_priority_to_enum(self, service):
        """Test mapping priority strings to enum."""
        from app.models.task import TaskPriority
        
        assert service.map_priority_to_enum("high") == TaskPriority.HIGH
        assert service.map_priority_to_enum("urgent") == TaskPriority.URGENT
        assert service.map_priority_to_enum("medium") == TaskPriority.MEDIUM
        assert service.map_priority_to_enum("low") == TaskPriority.LOW
        assert service.map_priority_to_enum("unknown") == TaskPriority.MEDIUM


class TestTaskExtractionIntegration:
    """Integration tests for task extraction (requires API key)."""
    
    @pytest.mark.skip(reason="Requires OpenAI API key")
    @pytest.mark.asyncio
    async def test_real_extraction(self):
        """Test actual LLM extraction (skip unless running integration tests)."""
        service = TaskExtractionService()
        
        transcript = """
        Manager: Let's discuss the Q4 deliverables. Alex, I need you to 
        complete the API documentation by end of next week. It's critical 
        for the client demo.
        
        Alex: Got it, I'll prioritize that.
        
        Manager: Jordan, can you set up the staging environment? 
        Low priority, whenever you have bandwidth.
        
        Jordan: Sure, I'll add it to my backlog.
        """
        
        tasks = await service.extract_tasks(transcript)
        
        assert len(tasks) >= 2
        assert any("API documentation" in t.title.lower() or "documentation" in t.title.lower() for t in tasks)
