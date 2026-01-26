"""Task type enumeration."""

from enum import Enum


class TaskType(str, Enum):
    """Task type enumeration for user tasks.
    
    Note: Database enum uses uppercase values to match PostgreSQL enum type.
    """

    NOTE_TAKING = "NOTE_TAKING"
    ADD_TO_KNOWLEDGE_BASE = "ADD_TO_KNOWLEDGE_BASE"
    QUESTION_ANSWER = "QUESTION_ANSWER"
    CREATE_TODO = "CREATE_TODO"
    CREATE_DIAGRAMS = "CREATE_DIAGRAMS"
    ADD_TO_GOOGLE_SHEETS = "ADD_TO_GOOGLE_SHEETS"
    CREATE_LOCATION_MAP = "CREATE_LOCATION_MAP"
    COMPARE_SHOPPING_PRICES = "COMPARE_SHOPPING_PRICES"
    CREATE_ACTION_FROM_CONTEXT = "CREATE_ACTION_FROM_CONTEXT"
    ADD_TO_CONTEXT = "ADD_TO_CONTEXT"
