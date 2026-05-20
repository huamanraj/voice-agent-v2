Mercury Voice Agent
===================

Production-ready telephony AI voice agent built around Ports and Adapters.

Current build status:
- Phase 0 complete: `uv` project, virtual environment, config, app shell, logging shell.
- Phase 1 complete: provider-neutral contracts for audio, packets, events, ports, and capabilities.
- Phase 2 complete: mock telephony, STT, TTS, LLM, and in-memory storage for offline simulation.
- Phase 3 complete: bounded queues, task lifecycle, EOS handling, and mock-session startup/shutdown.
- Phase 4 complete: sequence creation, invalidation, output gating, and stale audio dropping.
- Phase 5 complete: turn manager, expected-answer hints, local Smart Turn result handling, and Hinglish completion rules.
- Phase 6 complete: soft/hard interruption decisions, force phrases, backchannels, and cancellation hooks.
- Phase 7 complete: audio conversion, resampling, 20 ms chunking, routing, and rolling PCM16 16k buffer.

Local setup:
```powershell
$env:UV_CACHE_DIR = (Join-Path (Get-Location) '.uv-cache')
uv venv
uv sync
uv run python scripts/download_models.py
uv run python -c "import voice_agent"
```

Run the development API:
```powershell
uv run voice-agent
```

When VAD and Smart Turn are enabled, startup loads `models/silero_vad.onnx`
and `models/smart_turn_v3.onnx` before calls are accepted.
