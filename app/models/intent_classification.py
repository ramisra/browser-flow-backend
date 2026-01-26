"""Intent classification data models."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class IntentCategory(str, Enum):
    """Intent category enumeration."""

    DATA_COLLECTION = "DATA_COLLECTION"
    TASK_CREATION = "TASK_CREATION"
    INFORMATION_RETRIEVAL = "INFORMATION_RETRIEVAL"
    AUTOMATION = "AUTOMATION"
    ANALYSIS = "ANALYSIS"
    DOCUMENTATION = "DOCUMENTATION"
    INTEGRATION = "INTEGRATION"
    OTHER = "OTHER"


class IntentClassification(BaseModel):
    """Intent classification result."""

    category: IntentCategory = Field(..., description="Primary intent category")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")
    description: str = Field(..., description="Human-readable description of the intent")
    subcategories: List[str] = Field(default_factory=list, description="Additional subcategories")
    keywords: List[str] = Field(default_factory=list, description="Key terms extracted from context")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


__all__ = ["IntentClassification", "IntentCategory"]
