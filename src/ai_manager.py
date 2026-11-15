"""AIManager: composes GeminiClient + PromptBuilder; validates responses.

Keeps module-level analyze_event() wrapper for backward compatibility.
"""

import json
import logging
import re

from src.ai_client import GeminiClient, PromptBuilder
from src.base_manager import BaseManager
from src.exceptions import APIError, ResponseValidationError

logger = logging.getLogger(__name__)

ANALYSIS_SCHEMA = {
    "event_category": str,
    "career_relevance": int,
    "learning_value": int,
    "networking_value": int,
    "ai_reasoning": str,
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
        for key, expected in ANALYSIS_SCHEMA.items():
            if key not in data:
                return False
            if expected is int:
                if type(data[key]) is not int or not (1 <= data[key] <= 5):
                    return False
            elif expected is str:
                if not isinstance(data[key], str) or not data[key].strip():
                    return False
        return True

    def parse_response(self, raw: str) -> dict:
        json_text = raw
        if isinstance(raw, str):
            # Accept one complete Markdown JSON block around the whole response.
            fenced_json = re.fullmatch(
                r"```(?:json)?[ \t]*\r?\n(.*?)\r?\n```",
                raw.strip(), flags=re.DOTALL | re.IGNORECASE,
            )
            if fenced_json is not None:
                json_text = fenced_json.group(1)
        try:
            data = json.loads(json_text)
        except (json.JSONDecodeError, TypeError, UnicodeDecodeError) as exc:
            response_length = None
            empty = None
            fenced = None
            if isinstance(raw, (str, bytes, bytearray)):
                response_length = len(raw)
            if isinstance(raw, str):
                empty = not raw.strip()
                fenced = raw.lstrip().startswith("```")
            line = column = position = None
            if isinstance(exc, json.JSONDecodeError):
                line, column, position = exc.lineno, exc.colno, exc.pos
            # Never include raw text, prompts or exception tracebacks in diagnostics.
            logger.warning(
                "AI response JSON parsing failed response_type=%s length=%s "
                "empty=%s fenced=%s line=%s column=%s position=%s",
                type(raw).__name__, response_length, empty, fenced, line, column, position,
            )
            if isinstance(exc, json.JSONDecodeError):
                raise ResponseValidationError(f"Non-JSON response: {exc}") from exc
            raise ResponseValidationError("AI response did not contain valid JSON text.") from None
        if not self.validate_schema(data):
            raise ResponseValidationError("AI response failed schema validation.")
        return data

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

    def run(self) -> None:
        return None


# ----------------------------------------------------------------------
# Backward-compatible wrapper
# ----------------------------------------------------------------------
_default_ai = AIManager()


def analyze_event(profile: dict, name: str, description: str):
    return _default_ai.analyze_event(profile, name, description)
