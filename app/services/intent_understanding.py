"""Intent understanding service using Claude agent."""

import json
from typing import Any, Dict, Optional

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    query,
)

from app.models.intent_classification import IntentCategory, IntentClassification


class IntentUnderstandingService:
    """Service for understanding user intent from context."""

    async def understand_intent(
        self, context: str, context_metadata: Optional[Dict[str, Any]] = None
    ) -> IntentClassification:
        """Analyze user context and classify the intent.

        Args:
            context: User context text to analyze
            context_metadata: Optional metadata about the context (urls, tags, etc.)

        Returns:
            IntentClassification with category, confidence, and metadata
        """
        # Build context description
        context_info = context
        if context_metadata:
            if "urls" in context_metadata:
                context_info += f"\n\nURLs: {', '.join(context_metadata['urls'])}"
            if "tags" in context_metadata:
                context_info += f"\n\nTags: {', '.join(context_metadata['tags'])}"

        prompt = f"""
You are an intent classification expert. Analyze the following user context and determine what the user wants to accomplish.

User Context:
{context_info}

Your task is to:
1. Classify the primary intent into one of these categories:
   - DATA_COLLECTION: User wants to collect, gather, or extract data and store in google sheet.
   - TASK_CREATION: User wants to create tasks, todos, or action items
   - INFORMATION_RETRIEVAL: User wants to find, search, or retrieve information
   - AUTOMATION: User wants to automate a process or workflow
   - ANALYSIS: User wants to analyze, compare, or evaluate something
   - DOCUMENTATION: User wants to document, note, or record information
   - INTEGRATION: User wants to integrate with external services or tools
   - OTHER: Intent doesn't fit into the above categories

2. Provide a confidence score (0.0 to 1.0) indicating how certain you are about the classification
3. Extract key terms and keywords from the context
4. Identify any subcategories or secondary intents
5. Provide a clear description of what the user wants to do

Return your analysis as a JSON object with this exact structure:
{{
  "category": "one of the categories above",
  "confidence": 0.0-1.0,
  "description": "clear description of the intent",
  "subcategories": ["subcategory1", "subcategory2"],
  "keywords": ["keyword1", "keyword2", "keyword3"],
  "metadata": {{
    "reasoning": "brief explanation of why this category was chosen",
    "complexity": "simple|moderate|complex"
  }}
}}

Be precise and thoughtful in your classification. Consider the user's actual goal, not just surface-level keywords.
"""

        final_result: Optional[Dict[str, Any]] = None

        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                allowed_tools=["Read", "Edit", "Glob"],
                permission_mode="acceptEdits",
                system_prompt=(
                    "You are an expert at understanding user intent from context. "
                    "You classify intents accurately and provide detailed analysis."
                ),
            ),
        ):
            if isinstance(message, ResultMessage):
                # Extract text from result message
                if hasattr(message, "content"):
                    content = message.content
                    if isinstance(content, str):
                        try:
                            final_result = json.loads(content)
                        except json.JSONDecodeError:
                            # Try to extract JSON from text
                            import re

                            json_match = re.search(r"\{.*\}", content, re.DOTALL)
                            if json_match:
                                try:
                                    final_result = json.loads(json_match.group())
                                except json.JSONDecodeError:
                                    pass
                elif hasattr(message, "text"):
                    try:
                        final_result = json.loads(message.text)
                    except (json.JSONDecodeError, AttributeError):
                        pass

        # Parse and validate the result
        if not final_result:
            # Fallback classification
            return IntentClassification(
                category=IntentCategory.OTHER,
                confidence=0.5,
                description="Unable to determine intent from context",
                keywords=[],
            )

        try:
            # Validate category
            category_str = final_result.get("category", "OTHER").upper()
            try:
                category = IntentCategory(category_str)
            except ValueError:
                category = IntentCategory.OTHER

            return IntentClassification(
                category=category,
                confidence=float(final_result.get("confidence", 0.5)),
                description=final_result.get("description", "Intent analysis"),
                subcategories=final_result.get("subcategories", []),
                keywords=final_result.get("keywords", []),
                metadata=final_result.get("metadata", {}),
            )
        except (ValueError, KeyError, TypeError) as e:
            # Fallback on parsing errors
            return IntentClassification(
                category=IntentCategory.OTHER,
                confidence=0.5,
                description=f"Error parsing intent: {str(e)}",
                keywords=[],
            )


__all__ = ["IntentUnderstandingService"]
