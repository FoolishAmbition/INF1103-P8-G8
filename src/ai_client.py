"""Gemini HTTP client and prompt builder (composed by AIManager)."""

import os

from src.exceptions import APIError


class GeminiClient:
    def __init__(self, api_key: str | None = None, model_name: str = "gemini-3.5-flash-lite"):
        self._api_key = api_key or os.getenv("API_KEY", "")
        self._model_name = model_name

    def is_available(self) -> bool:
        return bool(self._api_key)

    def call(self, prompt: str) -> str:
        if not self.is_available():
            raise APIError("API_KEY is not set.")

        from google import genai
        from google.genai import types
        from google.genai.errors import APIError as GenAIAPIError
        from httpx import TransportError

        try:
            client = genai.Client(api_key=self._api_key)
            response = client.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            return response.text or ""
        except (TransportError, GenAIAPIError) as exc:
            raise APIError(f"Gemini call failed: {exc}") from exc
