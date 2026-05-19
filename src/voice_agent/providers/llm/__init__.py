"""LLM adapters package."""

from voice_agent.providers.llm.litellm import LiteLLM
from voice_agent.providers.llm.mock import MockLLM

__all__ = ["LiteLLM", "MockLLM"]
