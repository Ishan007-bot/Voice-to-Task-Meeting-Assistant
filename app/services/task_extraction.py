"""
Task Extraction Service - The GenAI Heart
Uses LangChain with GPT-4o and structured output for reliable task extraction.
"""

from datetime import date, datetime
from typing import List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.exceptions import TaskExtractionError
from app.core.logging import get_logger
from app.models.task import TaskPriority
from app.schemas.task import ExtractedTask, TaskExtractionResult

logger = get_logger(__name__)


# Pydantic model for structured output
class TaskSchema(BaseModel):
    """Schema for a single extracted task."""
    title: str = Field(description="Short descriptive title of the task")
    description: Optional[str] = Field(
        default=None,
        description="Detailed context of the task from the meeting",
    )
    priority: str = Field(
        default="Medium",
        description="Priority level: High, Medium, or Low based on speaker's tone and urgency",
    )
    assignee: str = Field(
        default="Unassigned",
        description="Name of the person assigned to this task, or 'Unassigned' if not specified",
    )
    due_date: str = Field(
        default="TBD",
        description="Due date in ISO-8601 format (YYYY-MM-DD), or 'TBD' if not mentioned",
    )


class TaskListSchema(BaseModel):
    """Schema for the list of extracted tasks."""
    tasks: List[TaskSchema] = Field(
        description="List of action items extracted from the meeting transcript"
    )


# The system prompt for task extraction
TASK_EXTRACTION_SYSTEM_PROMPT = """Role: You are a Senior Project Manager and Data Extraction Expert.
Task: Analyze the provided meeting transcript and extract a list of ACTION ITEMS.

Constraints:
1. ONLY extract concrete, actionable tasks that were explicitly discussed.
2. Do NOT create tasks from general discussion or opinions.
3. If a due date isn't mentioned, set it to "TBD".
4. Assign priority based on the speaker's tone and language:
   - "High": urgent words like "ASAP", "critical", "immediately", "must", "urgent"
   - "Medium": normal importance, standard deadlines
   - "Low": "when you have time", "nice to have", "eventually"
5. Extract the 'Assignee' only if a name is clearly linked to the task.
6. For each task, include relevant context in the description.
7. If the transcript contains no actionable tasks, return an empty list.

Focus on tasks that have:
- A clear action verb (create, update, fix, implement, review, etc.)
- Potentially an owner or assignee
- An implied or explicit deadline

Examples of action items:
- "John, can you update the documentation by Friday?"
- "We need to fix the login bug before the release."
- "Someone should review the security audit results."

Examples of NON-action items (do not extract):
- "I think we should consider redesigning the homepage." (just an opinion)
- "The sales numbers look good this quarter." (observation)
- "Let me know if you have any questions." (generic closing)"""


class TaskExtractionService:
    """
    Service for extracting actionable tasks from meeting transcripts.
    Uses LangChain with GPT-4o and structured output parsing.
    """
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.1,  # Low temperature for consistent extraction
        )
        
        # Create structured output parser
        self.structured_llm = self.llm.with_structured_output(TaskListSchema)
        
        # Create the prompt template
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", TASK_EXTRACTION_SYSTEM_PROMPT),
            ("human", """Meeting Transcript:
---
{transcript}
---

Extract all action items from this meeting transcript. If there are no actionable tasks, return an empty list.

Today's date is: {current_date}"""),
        ])
    
    async def extract_tasks(
        self,
        transcript: str,
        meeting_context: Optional[str] = None,
    ) -> List[ExtractedTask]:
        """
        Extract actionable tasks from a meeting transcript.
        
        Args:
            transcript: The full meeting transcript text
            meeting_context: Optional context about the meeting
            
        Returns:
            List of ExtractedTask objects
        """
        try:
            if not transcript or len(transcript.strip()) < 50:
                logger.warning("Transcript too short for task extraction")
                return []
            
            # Prepare input
            current_date = date.today().isoformat()
            
            # If transcript is very long, truncate with warning
            max_chars = 50000  # ~12k tokens
            if len(transcript) > max_chars:
                logger.warning(
                    "Transcript truncated for processing",
                    original_length=len(transcript),
                    truncated_to=max_chars,
                )
                transcript = transcript[:max_chars] + "\n\n[Transcript truncated due to length...]"
            
            # Build the chain
            chain = self.prompt | self.structured_llm
            
            # Execute extraction
            result: TaskListSchema = await chain.ainvoke({
                "transcript": transcript,
                "current_date": current_date,
            })
            
            # Convert to ExtractedTask format
            extracted_tasks = []
            for task in result.tasks:
                extracted_tasks.append(
                    ExtractedTask(
                        title=task.title,
                        description=task.description,
                        priority=self._normalize_priority(task.priority),
                        assignee=task.assignee,
                        due_date=task.due_date,
                    )
                )
            
            logger.info(
                "Tasks extracted successfully",
                task_count=len(extracted_tasks),
            )
            
            return extracted_tasks
            
        except Exception as e:
            logger.error("Task extraction failed", error=str(e))
            raise TaskExtractionError(f"Failed to extract tasks: {str(e)}")
    
    def _normalize_priority(self, priority: str) -> str:
        """Normalize priority to valid enum values."""
        priority_lower = priority.lower().strip()
        
        if priority_lower in ["high", "urgent", "critical"]:
            return "High"
        elif priority_lower in ["low", "minor"]:
            return "Low"
        else:
            return "Medium"
    
    def parse_due_date(self, due_date_str: str) -> Optional[date]:
        """
        Parse due date string to date object.
        Handles various formats including relative dates.
        """
        if not due_date_str or due_date_str.upper() == "TBD":
            return None
        
        try:
            # Try ISO format first
            return date.fromisoformat(due_date_str)
        except ValueError:
            pass
        
        try:
            # Try common formats
            from dateutil import parser as date_parser
            parsed = date_parser.parse(due_date_str, fuzzy=True)
            return parsed.date()
        except Exception:
            logger.warning(f"Could not parse due date: {due_date_str}")
            return None
    
    def map_priority_to_enum(self, priority: str) -> TaskPriority:
        """Map priority string to TaskPriority enum."""
        mapping = {
            "high": TaskPriority.HIGH,
            "urgent": TaskPriority.URGENT,
            "medium": TaskPriority.MEDIUM,
            "low": TaskPriority.LOW,
        }
        return mapping.get(priority.lower(), TaskPriority.MEDIUM)
