# AGENTS.md

## Project summary

This project is a real-time AI telephony voice agent backend for phone calls and calls are outbound for now.

The main pipeline is:

Call media stream
→ VAD/STT detects user speech
→ Turn manager decides the active user turn
→ LLM generates response
→ TTS creates audio
→ Playback sends audio back to the caller

The most important goal is smooth real-time calling with low latency, correct turn handling, and no broken interruption behavior.

## Reference implementation (bolna-master)

This repo follows the same voice-agent system design as [Bolna](https://github.com/bolna-ai/bolna). When exploring architecture, pipeline flow, provider wiring, or turn/interruption patterns, check the local **`bolna-master/`** folder at the repo root for working code examples.

- Use it as a **reference**, not something to copy blindly — adapt patterns to this project's structure (`src/mercury/`, `src/voice_agent/`, etc.).
- Prefer reading Bolna for design intent; implement changes in this codebase's modules and conventions.
- `bolna-master/` is gitignored; it may not exist in every checkout so search look wiki https://deepwiki.com/bolna-ai/bolna/2-architecture  https://deepwiki.com/bolna-ai/bolna/2.1-core-orchestration:-taskmanager  https://deepwiki.com/bolna-ai/bolna/4.2-conversational-agents  https://deepwiki.com/bolna-ai/bolna/5.4-telephony-integration  https://deepwiki.com/bolna-ai/bolna/6.1-interruption-handling  https://deepwiki.com/bolna-ai/bolna/2.3-queue-based-communication  



## Main coding rules

- Keep the call pipeline fast.
- Do not add blocking code inside websocket, audio streaming, STT, TTS, or playback paths.
- Use async code properly.
- Do not use `time.sleep()` in async code. Use `await asyncio.sleep()` instead.
- Do not make large refactors unless the task clearly needs it.
- Prefer small, safe changes.
- Always keep file context small and files modular 
- Dont hardcode thing or do quick fix
- Keep existing function names and file structure unless there is a strong reason to change them.
- Before making any chnage do deep research from web your knowledge is older
- Always read docs dont rely on your knowledge 


## Voice call behavior rules

- A user turn must not be mixed with the wrong AI question.
- If the user speaks while AI audio is playing, handle it carefully.
- If interruption is disabled globally, do not treat middle speech as the answer to the next question.
- When changing interruption logic, check these things:
  - current speech epoch
  - active turn id
  - current AI response id
  - pending TTS audio
  - playback queue
  - stale transcripts
- Never allow old TTS audio to play after a new user turn starts.
- Never allow an old LLM response to continue after it has been cancelled.
- When barge-in is enabled, stop current AI audio before starting the new response.
- When barge-in is disabled, do not corrupt the next question/answer mapping.

## Latency rules

- STT latency means: time from user speech/audio received to transcript becoming available.
- TTS latency means: time from text sent to TTS to first playable audio chunk.
- Optimize for first audio chunk, not only full audio completion.
- Avoid waiting for a full long sentence if streaming is possible.
- Log timing clearly when touching STT, TTS, LLM, websocket, or playback code.

## Important files

- `src/mercury/api/routes/vobiz/media_stream.py`
  - Main Vobiz media websocket handling.
  - Be extra careful here.
  - Small changes only unless requested.

- `src/mercury/telephony/vobiz/`
  - Vobiz telephony-specific code.

- `src/mercury/telephony/vobiz/tts_sarvam.py`
  - Sarvam TTS streaming logic.
  - Keep first-audio latency low.

- `src/mercury/`
  - Core backend logic.

- `tests/`
  - Add or update tests when changing important call logic.

## Logging rules

- Logs should help debug call issues.
- Add logs for:
  - user speech start
  - transcript received
  - AI response started
  - TTS first chunk received
  - playback started
  - interruption decision
  - cancellation decision
- Do not log secrets.
- Do not log full API keys.
- Avoid logging full phone numbers.
- Avoid logging full user transcripts unless needed for debugging.

## Safety rules

- Never hardcode API keys, database URLs, tokens, or passwords.
- Use environment variables.
- Do not commit `.env` files.
- Do not remove auth, validation, or rate limit logic without clear reason.

## Database rules

- Do not change database schema casually.
- If schema changes are needed, create a migration.
- Keep backward compatibility when possible.

## Testing rules

Before finishing a code change, run the most relevant checks.

Use these commands if available:

```bash
pytest
````

```bash
ruff check .
```

```bash
mypy .
```

If a command is missing or fails because of environment setup, explain clearly what happened.

## Style rules

* Write simple readable Python.
* Prefer clear names over clever code.
* Keep functions small when possible.
* Add comments only when the logic is hard to understand.
* Do not over-engineer.

## How to answer in this project

When explaining a change, include:

1. What was wrong
2. What was changed
3. Why it fixes the problem
4. What to test in a real call

Use simple English.




