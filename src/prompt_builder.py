"""Build sanitized prompts for AI event analysis."""

from src.exceptions import ValidationError


class PromptBuilder:
    """Create Gemini prompts without forwarding location or transit data."""

    def build_schema_instruction(self) -> str:
        return (
            "Respond ONLY with a valid JSON object (no markdown, no ```json code fences). "
            "The JSON object must contain exactly these keys: "
            "event_category (string), career_relevance (int 1-5), "
            "learning_value (int 1-5), networking_value (int 1-5), "
            "ai_reasoning (string)."
        )

    def build_analysis_prompt(self, profile: dict, name: str, description: str) -> str:
        if not isinstance(profile, dict):
            raise ValidationError("AI profile must be a dictionary.")
        safe_profile = {
            "field_of_study": profile.get("field_of_study", ""),
            "interests": profile.get("interests", []),
        }
        return (
            f"Student profile: {safe_profile}\n"
            f"Event name: {name}\n"
            f"Event description: {description}\n\n"
            f"{self.build_schema_instruction()}"
        )
