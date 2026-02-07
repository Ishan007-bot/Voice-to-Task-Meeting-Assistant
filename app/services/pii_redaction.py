"""
PII Redaction Service
Uses LLM to identify and mask sensitive data before storage.
"""

import hashlib
import re
from typing import Dict, List, Tuple

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class PIIEntity(BaseModel):
    """A detected PII entity."""
    text: str = Field(description="The original PII text")
    type: str = Field(description="Type of PII: email, phone, ssn, credit_card, password, api_key, address, name")
    start_index: int = Field(description="Start position in text")
    end_index: int = Field(description="End position in text")


class PIIDetectionResult(BaseModel):
    """Result of PII detection."""
    entities: List[PIIEntity] = Field(
        default=[],
        description="List of detected PII entities",
    )


# Common PII patterns for regex-based detection
PII_PATTERNS = {
    "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    "phone": r'\b(?:\+?1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
    "ssn": r'\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b',
    "credit_card": r'\b(?:\d{4}[-.\s]?){3}\d{4}\b',
    "ip_address": r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
    "api_key": r'\b(?:sk-|api[-_]?key[-_]?)[a-zA-Z0-9]{20,}\b',
}

PII_DETECTION_PROMPT = """You are a privacy protection specialist. Analyze the following text and identify any Personally Identifiable Information (PII) or sensitive data.

Look for:
1. Names of individuals
2. Email addresses
3. Phone numbers
4. Social Security Numbers
5. Credit card numbers
6. Passwords or credentials mentioned
7. API keys or tokens
8. Physical addresses
9. Company confidential information
10. Private IDs or account numbers

For each piece of PII found, identify:
- The exact text
- The type of PII
- The approximate start and end positions

Only flag actual PII. Do NOT flag:
- Generic job titles
- Company names (unless combined with sensitive info)
- General discussion of topics

Text to analyze:
---
{text}
---"""


class PIIRedactionService:
    """
    Service for detecting and redacting PII from transcripts.
    Combines regex patterns with LLM-based detection.
    """
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0,
        )
        self.structured_llm = self.llm.with_structured_output(PIIDetectionResult)
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", PII_DETECTION_PROMPT),
            ("human", "{text}"),
        ])
    
    async def detect_pii(self, text: str) -> List[PIIEntity]:
        """
        Detect PII in text using both regex and LLM.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of detected PII entities
        """
        entities = []
        
        # First pass: Regex-based detection (fast, reliable for patterns)
        regex_entities = self._detect_with_regex(text)
        entities.extend(regex_entities)
        
        # Second pass: LLM-based detection (catches context-dependent PII)
        try:
            llm_entities = await self._detect_with_llm(text)
            
            # Merge entities, avoiding duplicates
            for llm_entity in llm_entities:
                if not self._is_duplicate(llm_entity, entities):
                    entities.append(llm_entity)
                    
        except Exception as e:
            logger.warning("LLM PII detection failed, using regex only", error=str(e))
        
        logger.info(f"Detected {len(entities)} PII entities")
        return entities
    
    def _detect_with_regex(self, text: str) -> List[PIIEntity]:
        """Detect PII using regex patterns."""
        entities = []
        
        for pii_type, pattern in PII_PATTERNS.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                entities.append(PIIEntity(
                    text=match.group(),
                    type=pii_type,
                    start_index=match.start(),
                    end_index=match.end(),
                ))
        
        return entities
    
    async def _detect_with_llm(self, text: str) -> List[PIIEntity]:
        """Detect PII using LLM analysis."""
        # Only process chunks to avoid token limits
        max_chars = 10000
        if len(text) > max_chars:
            # Process in chunks
            entities = []
            for i in range(0, len(text), max_chars):
                chunk = text[i:i + max_chars]
                chunk_entities = await self._detect_with_llm(chunk)
                
                # Adjust indices for chunk offset
                for entity in chunk_entities:
                    entity.start_index += i
                    entity.end_index += i
                    entities.append(entity)
            
            return entities
        
        chain = self.prompt | self.structured_llm
        result: PIIDetectionResult = await chain.ainvoke({"text": text})
        return result.entities
    
    def _is_duplicate(
        self,
        entity: PIIEntity,
        existing: List[PIIEntity],
    ) -> bool:
        """Check if entity is a duplicate of an existing one."""
        for existing_entity in existing:
            # Check for overlapping ranges
            if (entity.start_index < existing_entity.end_index and
                entity.end_index > existing_entity.start_index):
                return True
        return False
    
    def redact_text(
        self,
        text: str,
        entities: List[PIIEntity],
    ) -> Tuple[str, Dict[str, str]]:
        """
        Redact PII from text.
        
        Args:
            text: Original text
            entities: List of PII entities to redact
            
        Returns:
            Tuple of (redacted_text, replacement_map)
        """
        if not entities:
            return text, {}
        
        # Sort entities by position (reverse order for safe replacement)
        sorted_entities = sorted(
            entities,
            key=lambda e: e.start_index,
            reverse=True,
        )
        
        redacted = text
        replacement_map = {}
        
        for entity in sorted_entities:
            # Create placeholder
            placeholder = f"[{entity.type.upper()}_REDACTED]"
            
            # Store mapping for potential recovery
            original_text = text[entity.start_index:entity.end_index]
            replacement_map[placeholder] = original_text
            
            # Replace in text
            redacted = (
                redacted[:entity.start_index] +
                placeholder +
                redacted[entity.end_index:]
            )
        
        return redacted, replacement_map
    
    async def redact_transcript(self, text: str) -> Tuple[str, str]:
        """
        Full pipeline: detect and redact PII from transcript.
        
        Args:
            text: Original transcript text
            
        Returns:
            Tuple of (redacted_text, original_hash)
        """
        # Store hash of original for verification
        original_hash = hashlib.sha256(text.encode()).hexdigest()
        
        # Detect PII
        entities = await self.detect_pii(text)
        
        if not entities:
            return text, original_hash
        
        # Redact
        redacted_text, _ = self.redact_text(text, entities)
        
        logger.info(
            "Transcript redacted",
            original_hash=original_hash[:16],
            entities_redacted=len(entities),
        )
        
        return redacted_text, original_hash
