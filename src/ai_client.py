"""Gemini HTTP client and prompt builder (composed by AIManager)."""

import os

from src.exceptions import APIError


class GeminiClient:
    def __init__(self, api_key: str | None = None, model_name: str = "gemini-2.5-flash"):
        self._api_key = api_key or os.getenv("API_KEY", "")
        self._model_name = model_name

    def is_available(self) -> bool:
        return bool(self._api_key)

    def call(self, prompt: str) -> str:
        if not self.is_available():
            raise APIError("API_KEY is not set.")
        try:
            from google import genai
            client = genai.Client(api_key=self._api_key)
            response = client.models.generate_content(
                model=self._model_name, contents=prompt
            )
            return response.text
        except Exception as exc:  # network/auth/API errors
            raise APIError(f"Gemini call failed: {exc}") from exc


class PromptBuilder:
    def build_schema_instruction(self) -> str:
        return (
            "Respond ONLY with JSON containing exactly these keys: "
            "event_category (string), career_relevance (int 1-5), "
            "learning_value (int 1-5), networking_value (int 1-5), "
            "ai_reasoning (string)."
        )

    def build_analysis_prompt(self, profile: dict, name: str, description: str) -> str:
        return (
            f"Student profile: {profile}\n"
            f"Event name: {name}\n"
            f"Event description: {description}\n\n"
            f"{self.build_schema_instruction()}"
        )