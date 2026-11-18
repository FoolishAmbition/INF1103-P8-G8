"""AIManager: composes GeminiClient + PromptBuilder; validates responses."""

import json

from src.ai_client import GeminiClient
from src.ai_scores import AIScores
from src.base_manager import BaseManager
from src.exceptions import APIError, ResponseValidationError, ValidationError
from src.prompt_builder import PromptBuilder

ANALYSIS_FIELDS = {
    "event_category",
    "career_relevance",
    "learning_value",
    "networking_value",
    "ai_reasoning",
}


class AIManager(BaseManager):
    def __init__(
        self,
        client: GeminiClient | None = None,
        prompt_builder: PromptBuilder | None = None,
        max_retries: int = 3,
    ):
        super().__init__(name="ai")
        self._client = client or GeminiClient()
        self._prompt_builder = prompt_builder or PromptBuilder()
        self._max_retries = max_retries

    def build_prompt(self, profile: dict, name: str, description: str) -> str:
        return self._prompt_builder.build_analysis_prompt(profile, name, description)

    def validate_schema(self, data: dict) -> bool:
        if not isinstance(data, dict):
            return False
        if set(data) != ANALYSIS_FIELDS:
            return False
        if not all(
            isinstance(data[field], str) and bool(data[field].strip())
            for field in ("event_category", "ai_reasoning")
        ):
            return False
        try:
            AIScores.from_dict(data)
        except ValidationError:
            return False
        return True

    def parse_response(self, raw: str) -> dict:
        if not raw or not isinstance(raw, str):
            raise ResponseValidationError("Empty response received from AI model.")

        text = raw.strip()

        # Strip markdown code fences if present (e.g. ```json ... ``` or ``` ... ```)
        if "```" in text:
            cleaned_lines = [
                line for line in text.splitlines()
                if not line.strip().startswith("```")
            ]
            text = "\n".join(cleaned_lines).strip()

        # If there is conversational text before or after, extract the JSON object
        if "{" in text and "}" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            text = text[start:end]

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ResponseValidationError(f"Non-JSON response: {exc}") from exc

        if not self.validate_schema(data):
            raise ResponseValidationError("AI response failed schema validation.")
        ai_scores = AIScores.from_dict(data)
        return {
            "event_category": data["event_category"],
            "ai_scores": ai_scores,
            "ai_reasoning": data["ai_reasoning"],
        }

    def analyze_event(self, profile: dict, name: str, description: str):
        if not self._client.is_available():
            return None, "API key not configured."
        prompt = self.build_prompt(profile, name, description)
        last_error = "Unknown API error."
        for _ in range(self._max_retries):
            try:
                raw = self._client.call(prompt)
                return self.parse_response(raw), None
            except APIError as exc:
                last_error = str(exc)
            except ResponseValidationError as exc:
                last_error = str(exc)
                # schema errors are unlikely to fix on retry; break
                break
        return None, last_error

