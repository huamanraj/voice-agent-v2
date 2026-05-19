"""Telephony adapters package."""

from voice_agent.providers.telephony.mock import MockTelephony
from voice_agent.providers.telephony.vobiz import VobizTelephony

__all__ = ["MockTelephony", "VobizTelephony"]
