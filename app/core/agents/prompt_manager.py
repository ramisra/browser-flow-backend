"""Prompt management component for agents."""

from typing import Any, Dict, List, Optional


class PromptManager:
    """Manages prompts for reasoning, system prompts, and prompt templates."""

    def __init__(
        self,
        system_prompt: Optional[str] = None,
        prompt_templates: Optional[Dict[str, str]] = None,
    ):
        """Initialize the prompt manager.

        Args:
            system_prompt: Default system prompt for the agent
            prompt_templates: Dictionary of prompt templates by name
        """
        self.system_prompt = system_prompt or ""
        self.prompt_templates = prompt_templates or {}

    def get_system_prompt(self) -> str:
        """Get the system prompt."""
        return self.system_prompt

    def set_system_prompt(self, prompt: str) -> None:
        """Set the system prompt."""
        self.system_prompt = prompt

    def register_template(self, name: str, template: str) -> None:
        """Register a prompt template.

        Args:
            name: Template name
            template: Template string with {placeholders}
        """
        self.prompt_templates[name] = template

    def get_template(self, name: str) -> Optional[str]:
        """Get a prompt template by name.

        Args:
            name: Template name

        Returns:
            Template string or None if not found
        """
        return self.prompt_templates.get(name)

    def format_prompt(
        self, template_name: str, **kwargs: Any
    ) -> str:
        """Format a prompt template with provided values.

        Args:
            template_name: Name of the template to use
            **kwargs: Values to fill in template placeholders

        Returns:
            Formatted prompt string

        Raises:
            ValueError: If template not found
        """
        template = self.get_template(template_name)
        if not template:
            raise ValueError(f"Template '{template_name}' not found")

        try:
            return template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing template parameter: {e}")

    def build_reasoning_prompt(
        self,
        task_description: str,
        context: Optional[Dict[str, Any]] = None,
        additional_instructions: Optional[str] = None,
    ) -> str:
        """Build a reasoning prompt for the agent.

        Args:
            task_description: Description of the task
            context: Optional context dictionary
            additional_instructions: Optional additional instructions

        Returns:
            Complete reasoning prompt
        """
        prompt_parts = [self.system_prompt]

        if task_description:
            prompt_parts.append(f"\nTask: {task_description}")

        if context:
            context_str = "\n".join(
                f"{k}: {v}" for k, v in context.items()
            )
            prompt_parts.append(f"\nContext:\n{context_str}")

        if additional_instructions:
            prompt_parts.append(f"\nAdditional Instructions:\n{additional_instructions}")

        return "\n".join(prompt_parts)


__all__ = ["PromptManager"]
