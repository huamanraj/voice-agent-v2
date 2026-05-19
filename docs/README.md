# Docs index

This file indexes the documentation under `docs/` so it's easy to search and navigate.

## Structure

- `docs/`
  - `cartesia/` -- Cartesia STT/TTS notes and WebSocket usage
    - `stt.md` -- Cartesia Speech-to-Text (streaming) docs/notes
    - `TTS WebSocket.md` -- Cartesia TTS WebSocket docs/notes
    - `tts.md` -- Cartesia Text-to-Speech (WebSocket) docs/notes
  - `deepgram/` -- Deepgram STT/TTS WebSocket notes
    - `stt.md` -- Deepgram Live Audio transcription (STT) WebSocket endpoint notes
    - `tts.md` -- Deepgram Continuous Text Stream (TTS) WebSocket endpoint notes
  - `lite-llm/` -- LiteLLM client notes
    - `pysdk.md` -- LiteLLM Python SDK usage (incl. streaming)
  - `plan/` -- Voice agent deep implementation plan (multi-part)
    - `00_MAIN_README.txt` -- Goal + high-level plan for a production voice agent
    - `01_SYSTEM_OVERVIEW.txt` -- System overview (high level)
    - `02_ARCHITECTURE_PATTERN_AND_PROVIDER_PORTS.txt` -- Hexagonal architecture + provider ports/adapters
    - `03_AGENT_PACKET_AND_EVENTS.txt` -- Standard agent packet + event schema
    - `04_QUEUE_BASED_TASK_ORCHESTRATION.txt` -- Queue-based orchestration between pipeline stages
    - `05_PROJECT_STRUCTURE.txt` -- Proposed folder/project structure
    - `06_CONFIGURATION.txt` -- Environment + agent configuration conventions
    - `07_TELEPHONY_VOBIZ_ADAPTER.txt` -- Vobiz streaming WebSocket adapter (TelephonyPort)
    - `08_AUDIO_PIPELINE.txt` -- Audio pipeline: conversion/chunking/routing/buffer
    - `09_STT_PIPELINE.txt` -- STT pipeline: transcripts + speech events
    - `10_TURN_DETECTION.txt` -- Turn detection: end-of-speech decisions
    - `11_INTERRUPTION_MANAGER.txt` -- Barge-in / interruption handling
    - `12_LLM_PIPELINE.txt` -- LLM pipeline: response generation for voice
    - `13_TTS_PIPELINE.txt` -- TTS pipeline: low-latency speech synthesis
    - `14_PLAYBACK_TRACKING_AND_CONTEXT.txt` -- Playback tracking + accurate conversation state
    - `15_STORAGE_PERSISTENCE.txt` -- Storage + persistence approach
    - `16_OBSERVABILITY_AND_LATENCY.txt` -- Observability + latency debugging
    - `17_ASSISTANT_MANAGER_AND_POST_CALL_TASKS.txt` -- Assistant manager + post-call tasks
    - `18_TESTING_PLAN.txt` -- Testing strategy
    - `19_BUILD_PHASES.txt` -- Build phases / suggested implementation order
    - `20_ACCEPTANCE_CHECKLIST.txt` -- Acceptance checklist
    - `21_AI_CODING_AGENT_PROMPT.txt` -- Prompt template for an AI coding agent
    - `22_REFERENCE_NOTES.txt` -- References + notes used to assemble the plan
    - `23_IMPLEMENTATION_STATUS_TEMPLATE.txt` -- Status template for tracking implementation
    - `99_FILE_MANIFEST.txt` -- Manifest of plan files (zip/file list)
  - `sarvam/` -- Sarvam SDK + STT/TTS WebSocket notes
    - `sdk.md` -- Sarvam Python library overview/usage
    - `stt.md` -- Sarvam real-time STT WebSocket endpoint notes
    - `tts.md` -- Sarvam real-time TTS WebSocket endpoint notes
  - `vobiz/` -- Vobiz streaming + WebSocket notes
    - `sdk.md` -- Vobiz Voice XML Streaming WebSockets overview
    - `streaming.md` -- Vobiz streaming WebSockets notes
    - `ws.md` -- Vobiz WebSocket notes
