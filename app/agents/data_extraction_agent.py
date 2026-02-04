"""Data extraction agent for extracting structured data and writing to Excel."""

import json
from typing import Any, Dict, List, Optional

from app.core.agents.agent_context import AgentContext
from app.core.agents.base_agent import BaseAgent
from app.core.agents.evaluator import Evaluator
from app.core.agents.prompt_manager import PromptManager
from app.core.agents.reasoning_engine import ReasoningEngine
from app.core.agents.tool_integration import ToolIntegration
from app.core.tools.excel_tools import ExcelTools
from app.models.agent_result import AgentResult


class DataExtractionAgent(BaseAgent):
    """Agent for extracting structured data and writing to Excel."""

    def __init__(
        self,
        agent_id: str,
        prompt_manager: PromptManager,
        tool_integration: ToolIntegration,
        evaluator: Evaluator,
        reasoning_engine: ReasoningEngine,
        excel_tools: Optional[ExcelTools] = None,
        semantic_knowledge: Optional[Any] = None,
        agent_context: Optional[AgentContext] = None,
    ):
        """Initialize the data extraction agent.

        Args:
            agent_id: Agent identifier
            prompt_manager: Prompt manager
            tool_integration: Tool integration
            evaluator: Evaluator
            reasoning_engine: Reasoning engine
            excel_tools: Optional Excel tools instance
            semantic_knowledge: Optional semantic knowledge service
            agent_context: Optional agent context
        """
        super().__init__(
            agent_id=agent_id,
            prompt_manager=prompt_manager,
            tool_integration=tool_integration,
            evaluator=evaluator,
            reasoning_engine=reasoning_engine,
            semantic_knowledge=semantic_knowledge,
            agent_context=agent_context,
        )
        self.excel_tools = excel_tools or ExcelTools()

        # Set up system prompt for data extraction
        system_prompt = """You are a data extraction specialist. Your task is to:
1. Parse unstructured text data (comma-separated, natural language, etc.)
2. Extract structured data points (names, titles, companies, numbers, etc.)
3. Understand user instructions for column requirements
4. Structure data into rows and columns
5. Handle multiple entries in various formats

Be precise and extract all relevant information."""
        self.prompt_manager.set_system_prompt(system_prompt)

    def _parse_columns_from_input(
        self,
        input_data: Optional[Dict[str, Any]],
        allow_key_fallback: bool = False,
    ) -> List[str]:
        """Parse column names from structured input data."""
        if not input_data:
            return []

        candidates = None
        if "columns" in input_data:
            candidates = input_data.get("columns")
        elif "fields" in input_data:
            candidates = input_data.get("fields")
        elif "headers" in input_data:
            candidates = input_data.get("headers")
        elif allow_key_fallback and isinstance(input_data, dict) and input_data:
            candidates = list(input_data.keys())

        if not candidates:
            return []

        if isinstance(candidates, str):
            columns = [col.strip() for col in candidates.split(",")]
        elif isinstance(candidates, dict):
            columns = list(candidates.keys())
        elif isinstance(candidates, list):
            columns = [str(col).strip() for col in candidates if str(col).strip()]
        else:
            return []

        seen = set()
        normalized = []
        for col in columns:
            if not col:
                continue
            if col in seen:
                continue
            seen.add(col)
            normalized.append(col)
        return normalized

    def _parse_json_array(self, text: str) -> List[Dict[str, Any]]:
        """Extract JSON array of objects from model text."""
        if not text:
            return []
        try:
            start_idx = text.find("[")
            end_idx = text.rfind("]") + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = text[start_idx:end_idx]
                parsed_data = json.loads(json_str)
                if isinstance(parsed_data, list):
                    return parsed_data
        except Exception:
            return []
        return []

    def _parse_sheet_name_from_input(
        self, input_data: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        """Extract sheet name from structured input data."""
        if not input_data:
            return None
        for key in ("sheet_name", "sheet", "worksheet", "tab_name"):
            value = input_data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _parse_file_name_from_input(
        self,
        input_data: Optional[Dict[str, Any]],
        sheet_name: Optional[str],
    ) -> Optional[str]:
        """Extract or derive Excel file name from input data."""
        file_name = None
        if input_data:
            for key in ("file_name", "filename", "file", "excel_file_name"):
                value = input_data.get(key)
                if isinstance(value, str) and value.strip():
                    file_name = value.strip()
                    break
        if not file_name and sheet_name:
            file_name = sheet_name
        if not file_name:
            return None
        if not file_name.lower().endswith(".xlsx"):
            file_name = f"{file_name}.xlsx"
        return file_name

    async def _extract_structured_data(
        self, text: str, columns: List[str], user_context: str
    ) -> List[Dict[str, Any]]:
        """Extract structured data from text using the reasoning engine."""
        if not text:
            return []
        print(
            "DataExtractionAgent: extracting structured data",
            f"columns={columns}",
            f"text_length={len(text)}",
        )

        if columns:
            column_list = ", ".join(columns)
            prompt = f"""Parse the following text and extract structured data for these columns: {column_list}.

Return a JSON array of objects. Each object should contain exactly these keys:
{columns}

Text to parse:
{text}"""
        else:
            prompt = f"""Parse the following text and extract structured data.

Infer appropriate column names from the content. Return a JSON array of objects,
where each object represents one entry.

Text to parse:
{text}"""

        result = await self.reason(
            prompt,
            context={"user_context": user_context},
        )

        reasoning_text = result.get("result", "")
        parsed = self._parse_json_array(reasoning_text)
        print(
            "DataExtractionAgent: parsed structured data",
            f"rows={len(parsed)}",
        )
        return parsed

    def _normalize_data(
        self, data: List[Dict[str, Any]], columns: List[str]
    ) -> List[Dict[str, Any]]:
        """Normalize rows to ensure all columns exist."""
        normalized_data = []
        for row in data:
            normalized_row = {col: row.get(col, "") for col in columns}
            normalized_data.append(normalized_row)
        return normalized_data

    async def execute(
        self, task_input: Dict[str, Any], agent_context: Optional[AgentContext] = None
    ) -> AgentResult:
        """Execute data extraction and Excel writing.

        Uses task identification input for columns and sheet naming,
        extracts structured data via the reasoning engine, then creates
        or appends to the Excel file.

        Args:
            task_input: Task input with selected_text, user_context, etc.
            agent_context: Optional agent context

        Returns:
            AgentResult with extracted data and Excel file path
        """
        try:
            print(
                "DataExtractionAgent: execute start",
                f"task_input_keys={list(task_input.keys())}",
            )
            selected_text = task_input.get("selected_text", "")
            user_context_text = task_input.get("user_context", "")
            if agent_context:
                user_context_text = user_context_text or agent_context.user_context
            print(
                "DataExtractionAgent: resolved context",
                f"selected_text_len={len(selected_text)}",
                f"user_context_len={len(user_context_text)}",
            )

            context_input = None
            if agent_context and agent_context.task_identification:
                context_input = agent_context.task_identification.input
            print(
                "DataExtractionAgent: context input",
                f"has_context_input={bool(context_input)}",
            )

            columns = self._parse_columns_from_input(
                context_input, allow_key_fallback=True
            )
            if not columns:
                columns = self._parse_columns_from_input(
                    task_input, allow_key_fallback=False
                )
            print(
                "DataExtractionAgent: resolved columns",
                f"columns={columns}",
            )

            sheet_name = self._parse_sheet_name_from_input(context_input)
            if not sheet_name:
                sheet_name = self._parse_sheet_name_from_input(task_input)
            file_name = self._parse_file_name_from_input(
                context_input, sheet_name
            )
            if not file_name:
                file_name = self._parse_file_name_from_input(task_input, sheet_name)
            print(
                "DataExtractionAgent: resolved sheet/file",
                f"sheet_name={sheet_name}",
                f"file_name={file_name}",
            )
        
            source_text = selected_text or user_context_text
            print(
                "DataExtractionAgent: source text",
                f"source_text_len={len(source_text)}",
            )
            extracted_data = await self._extract_structured_data(
                source_text, columns, user_context_text
            )
            print(
                "DataExtractionAgent: extracted data",
                f"rows={len(extracted_data)}",
            )

            if not extracted_data:
                print("DataExtractionAgent: no data extracted, failing")
                return AgentResult(
                    status="failed",
                    result={"error": "No data extracted from input."},
                    error="No data extracted from input.",
                )

            if not columns:
                columns = list(extracted_data[0].keys()) if extracted_data else []
            if not columns:
                columns = ["data"]
            print(
                "DataExtractionAgent: final columns",
                f"columns={columns}",
            )

            normalized_data = self._normalize_data(extracted_data, columns)
            print(
                "DataExtractionAgent: normalized data",
                f"rows={len(normalized_data)}",
            )
            excel_file_path = None
            if file_name:
                file_path = self.excel_tools.storage_dir / file_name
                if file_path.exists():
                    print(
                        "DataExtractionAgent: appending to existing file",
                        f"excel_file_path={file_path}",
                    )
                    await self.excel_tools.append_to_excel(
                        file_path=str(file_path),
                        data=normalized_data,
                        columns=columns,
                        sheet_name=sheet_name,
                    )
                    excel_file_path = str(file_path)
            if not excel_file_path:
                excel_file_path = await self.excel_tools.create_excel_file(
                    data=normalized_data,
                    columns=columns,
                    file_name=file_name,
                    sheet_name=sheet_name,
                )
            print(
                "DataExtractionAgent: excel file created",
                f"excel_file_path={excel_file_path}",
            )

            evaluation = await self.evaluate(
                normalized_data,
                expected_output={
                    "required_fields": columns,
                    "field_types": {col: "string" for col in columns},
                },
            )
            print(
                "DataExtractionAgent: evaluation complete",
                f"score={evaluation.score}",
                f"errors={evaluation.errors}",
            )

            return AgentResult(
                status="completed",
                result={
                    "excel_file_path": excel_file_path,
                    "extracted_data": normalized_data,
                    "columns": columns,
                    "row_count": len(normalized_data),
                },
                excel_file_path=excel_file_path,
                extracted_data=normalized_data,
                validation_errors=evaluation.errors,
                execution_metadata={
                    "evaluation_score": evaluation.score,
                    "evaluation_feedback": evaluation.feedback,
                },
            )

        except Exception as e:
            print("DataExtractionAgent: execution failed", f"error={e}")
            return AgentResult(
                status="failed",
                result={"error": str(e)},
                error=str(e),
            )


__all__ = ["DataExtractionAgent"]
