"""
Task Deduplication Service
Uses semantic similarity to prevent duplicate tasks.
"""

from typing import List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.task import Task
from app.repositories.task import TaskRepository
from app.services.embedding import EmbeddingService

logger = get_logger(__name__)


class DeduplicationService:
    """
    Service for detecting and handling duplicate tasks.
    Uses text embeddings for semantic comparison.
    """
    
    # Similarity threshold for considering tasks as duplicates
    SIMILARITY_THRESHOLD = 0.85
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.task_repo = TaskRepository(session)
        self.embedding_service = EmbeddingService()
    
    async def check_for_duplicates(
        self,
        task_title: str,
        task_description: Optional[str],
        user_id: str,
        threshold: float = None,
    ) -> List[Tuple[Task, float]]:
        """
        Check if similar tasks already exist for this user.
        
        Args:
            task_title: Title of the new task
            task_description: Description of the new task
            user_id: User ID to search within
            threshold: Similarity threshold (default: 0.85)
            
        Returns:
            List of (Task, similarity_score) tuples for similar tasks
        """
        try:
            threshold = threshold or self.SIMILARITY_THRESHOLD
            
            # Create combined text for embedding
            text = task_title
            if task_description:
                text = f"{task_title}\n{task_description}"
            
            # Generate embedding
            embedding = await self.embedding_service.get_embedding(text)
            
            # Search for similar tasks using pgvector
            similar_tasks = await self.task_repo.find_similar_tasks(
                embedding=embedding,
                user_id=user_id,
                threshold=threshold,
                limit=5,
            )
            
            if similar_tasks:
                logger.info(
                    "Found similar tasks",
                    task_title=task_title,
                    similar_count=len(similar_tasks),
                )
            
            return similar_tasks
            
        except Exception as e:
            logger.error("Duplicate check failed", error=str(e))
            # Don't fail the whole operation for deduplication errors
            return []
    
    async def deduplicate_tasks(
        self,
        tasks: List[Task],
        user_id: str,
    ) -> List[Task]:
        """
        Check list of tasks for duplicates against existing tasks.
        Marks duplicates accordingly.
        
        Args:
            tasks: List of new tasks to check
            user_id: User ID
            
        Returns:
            List of tasks with duplicate flags set
        """
        try:
            for task in tasks:
                # Check against existing tasks
                similar = await self.check_for_duplicates(
                    task_title=task.title,
                    task_description=task.description,
                    user_id=user_id,
                )
                
                if similar:
                    # Mark as duplicate of the most similar task
                    most_similar_task, similarity_score = similar[0]
                    
                    await self.task_repo.mark_as_duplicate(
                        task_id=task.id,
                        duplicate_of_id=most_similar_task.id,
                        similarity_score=similarity_score,
                    )
                    
                    logger.info(
                        "Task marked as duplicate",
                        task_id=task.id,
                        duplicate_of=most_similar_task.id,
                        similarity=similarity_score,
                    )
            
            return tasks
            
        except Exception as e:
            logger.error("Task deduplication failed", error=str(e))
            return tasks
    
    async def generate_task_embedding(self, task: Task) -> List[float]:
        """Generate and store embedding for a task."""
        text = task.title
        if task.description:
            text = f"{task.title}\n{task.description}"
        
        embedding = await self.embedding_service.get_embedding(text)
        
        # Update task with embedding
        await self.task_repo.update(task.id, {"embedding": embedding})
        
        return embedding
    
    async def bulk_generate_embeddings(self, tasks: List[Task]) -> None:
        """Generate embeddings for multiple tasks efficiently."""
        texts = []
        for task in tasks:
            text = task.title
            if task.description:
                text = f"{task.title}\n{task.description}"
            texts.append(text)
        
        embeddings = await self.embedding_service.get_embeddings_batch(texts)
        
        for task, embedding in zip(tasks, embeddings):
            await self.task_repo.update(task.id, {"embedding": embedding})
