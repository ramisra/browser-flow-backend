"""Evaluator component for agents."""

from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field


class EvaluationResult(BaseModel):
    """Result of an evaluation."""

    passed: bool = Field(..., description="Whether evaluation passed")
    score: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Evaluation score (0-1)"
    )
    feedback: str = Field(
        default="", description="Feedback message"
    )
    errors: List[str] = Field(
        default_factory=list, description="List of errors found"
    )
    warnings: List[str] = Field(
        default_factory=list, description="List of warnings"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class Evaluator:
    """Evaluates agent outputs and execution quality."""

    def __init__(
        self,
        validation_rules: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the evaluator.

        Args:
            validation_rules: Dictionary of validation rules
        """
        self.validation_rules = validation_rules or {}

    async def evaluate(
        self,
        result: Any,
        expected_output: Optional[Dict[str, Any]] = None,
        validation_criteria: Optional[Dict[str, Any]] = None,
    ) -> EvaluationResult:
        """Evaluate a result.

        Args:
            result: Result to evaluate
            expected_output: Optional expected output structure
            validation_criteria: Optional validation criteria

        Returns:
            EvaluationResult
        """
        criteria = validation_criteria or self.validation_rules
        errors = []
        warnings = []
        score = 1.0

        # Basic validation
        if result is None:
            errors.append("Result is None")
            score = 0.0
        elif isinstance(result, dict):
            # Check required fields if expected_output provided
            if expected_output:
                required_fields = expected_output.get("required_fields", [])
                for field in required_fields:
                    if field not in result:
                        errors.append(f"Missing required field: {field}")
                        score -= 0.1

            # Check data types
            if expected_output and "field_types" in expected_output:
                field_types = expected_output["field_types"]
                for field, expected_type in field_types.items():
                    if field in result:
                        actual_type = type(result[field]).__name__
                        if actual_type != expected_type:
                            warnings.append(
                                f"Field '{field}' has type {actual_type}, "
                                f"expected {expected_type}"
                            )
                            score -= 0.05

        # Apply custom validation rules
        if criteria:
            for rule_name, rule_func in criteria.items():
                if callable(rule_func):
                    try:
                        rule_result = rule_func(result)
                        if not rule_result:
                            errors.append(f"Validation rule '{rule_name}' failed")
                            score -= 0.1
                    except Exception as e:
                        warnings.append(
                            f"Error in validation rule '{rule_name}': {e}"
                        )

        score = max(0.0, min(1.0, score))

        return EvaluationResult(
            passed=len(errors) == 0,
            score=score,
            feedback=self._generate_feedback(errors, warnings, score),
            errors=errors,
            warnings=warnings,
        )

    def _generate_feedback(
        self,
        errors: List[str],
        warnings: List[str],
        score: float,
    ) -> str:
        """Generate feedback message.

        Args:
            errors: List of errors
            warnings: List of warnings
            score: Evaluation score

        Returns:
            Feedback message
        """
        if score == 1.0:
            return "Evaluation passed with no issues."

        feedback_parts = []
        if errors:
            feedback_parts.append(f"Errors: {', '.join(errors)}")
        if warnings:
            feedback_parts.append(f"Warnings: {', '.join(warnings)}")
        feedback_parts.append(f"Score: {score:.2f}")

        return ". ".join(feedback_parts)

    def add_validation_rule(
        self, name: str, rule: Callable[[Any], bool]
    ) -> None:
        """Add a custom validation rule.

        Args:
            name: Rule name
            rule: Validation function that takes result and returns bool
        """
        self.validation_rules[name] = rule


__all__ = ["Evaluator", "EvaluationResult"]
