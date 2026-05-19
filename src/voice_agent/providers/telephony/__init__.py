"""Telephony adapters package."""

from voice_agent.providers.telephony.mock import MockTelephony
from voice_agent.providers.telephony.vobiz import VobizTelephony
from voice_agent.providers.telephony.vobiz_outbound import VobizOutboundCall, VobizOutboundClient

__all__ = ["MockTelephony", "VobizOutboundCall", "VobizOutboundClient", "VobizTelephony"]
