"""Personality-Based Security Questions.

AI-driven, privacy-opt-in authentication that replaces static knowledge-based
questions with dynamically-generated challenges grounded in a user's
conversational history. Inference runs through the existing
``ai_assistant.ClaudeService`` wrapped in a thin adapter that enforces a
Pydantic output schema so responses are always machine-readable.
"""

default_app_config = "personality_auth.apps.PersonalityAuthConfig"
