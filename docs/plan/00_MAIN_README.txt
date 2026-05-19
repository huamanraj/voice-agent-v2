VOICE AGENT DEEP IMPLEMENTATION PLAN
====================================

Goal:
Build a production-ready telephony AI voice agent with accurate listening, fast replies, strong interruption/barge-in, and provider-swappable architecture.

This zip is optimized for AI coding agents.
Each file is one implementation area.
Read files in order.

Recommended stack:
- Runtime: Python, FastAPI, asyncio, uvicorn
- Telephony: Vobiz Streaming WebSocket first
- STT: Deepgram Nova-3 primary, Sarvam STT optional for Hindi/Hinglish testing
- TTS: Cartesia Sonic 3.5 primary, Sarvam Bulbul v3 optional backup
- LLM: LiteLLM (unified client) targeting Groq/OpenAI-compatible streaming models
- Turn detection: STT + local VAD + Smart-Turn + silence timers
- Interruption: telephony clear playback + TTS cancel + LLM cancel + sequence invalidation
- Live state: Redis
- Final storage: Postgres
- Observability: structured per-call logs + latency metrics

Main architecture pattern:
Ports and Adapters / Hexagonal Architecture.

Core rule:
Core agent must not import provider implementations directly.

Correct:
core/session.py uses TelephonyPort, STTPort, TTSPort, LLMPort.

Wrong:
core/session.py imports VobizAdapter, DeepgramAdapter, CartesiaAdapter directly.

Why this plan is better:
- Uses Bolna-style queue/task orchestration.
- Adds stronger provider-swappable contracts.
- Adds Vobiz clearAudio/checkpoint/playedStream support.
- Adds sequence IDs and output gate to prevent stale audio.
- Adds turn detection with VAD + Smart-Turn + transcript rules.
- Adds deep logging and latency tracking.
- Splits every pipeline step into implementable files.

File reading order:
01_SYSTEM_OVERVIEW.txt
02_ARCHITECTURE_PATTERN_AND_PROVIDER_PORTS.txt
03_AGENT_PACKET_AND_EVENTS.txt
04_QUEUE_BASED_TASK_ORCHESTRATION.txt
05_PROJECT_STRUCTURE.txt
06_CONFIGURATION.txt
07_TELEPHONY_VOBIZ_ADAPTER.txt
08_AUDIO_PIPELINE.txt
09_STT_PIPELINE.txt
10_TURN_DETECTION.txt
11_INTERRUPTION_MANAGER.txt
12_LLM_PIPELINE.txt
13_TTS_PIPELINE.txt
14_PLAYBACK_TRACKING_AND_CONTEXT.txt
15_STORAGE_PERSISTENCE.txt
16_OBSERVABILITY_AND_LATENCY.txt
17_ASSISTANT_MANAGER_AND_POST_CALL_TASKS.txt
18_TESTING_PLAN.txt
19_BUILD_PHASES.txt
20_ACCEPTANCE_CHECKLIST.txt
21_AI_CODING_AGENT_PROMPT.txt
22_REFERENCE_NOTES.txt

Main implementation approach:
1. Build contracts first.
2. Build mock providers second.
3. Build core orchestration with mocks.
4. Build Vobiz adapter.
5. Build STT/TTS/LLM adapters.
6. Build interruption and turn detection.
7. Add storage/logging.
8. Test with mock calls before real calls.
9. Test real Vobiz calls.
10. Tune thresholds from logs.

Important rule for interruption:
Never trust cancellation alone.
Always invalidate sequence IDs and drop stale chunks.
