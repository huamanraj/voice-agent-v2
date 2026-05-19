Mercury Voice Agent
===================

Production-ready telephony AI voice agent built around Ports and Adapters.

Current build status:
- Phase 0 complete: `uv` project, virtual environment, config, app shell, logging shell.
- Phase 1 complete: provider-neutral contracts for audio, packets, events, ports, and capabilities.
- Phase 2 complete: mock telephony, STT, TTS, LLM, and in-memory storage for offline simulation.

Local setup:
```powershell
$env:UV_CACHE_DIR = (Join-Path (Get-Location) '.uv-cache')
uv venv
uv sync
uv run python -c "import voice_agent"
```

Run the development API:
```powershell
uv run voice-agent
```
