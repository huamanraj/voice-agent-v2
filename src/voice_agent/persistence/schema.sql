CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    system_prompt TEXT NOT NULL,
    provider_overrides JSONB NOT NULL DEFAULT '{}'::jsonb,
    voice_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    language_default TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS calls (
    call_id TEXT PRIMARY KEY,
    agent_id TEXT REFERENCES agents(agent_id),
    caller TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ,
    end_reason TEXT,
    transcript_summary TEXT,
    error_count INTEGER NOT NULL DEFAULT 0,
    raw_record JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS turns (
    id BIGSERIAL PRIMARY KEY,
    call_id TEXT NOT NULL REFERENCES calls(call_id) ON DELETE CASCADE,
    turn_index INTEGER NOT NULL,
    speaker TEXT NOT NULL CHECK (speaker IN ('user', 'assistant', 'tool')),
    text TEXT,
    full_text TEXT,
    heard_text TEXT,
    interrupted BOOLEAN NOT NULL DEFAULT false,
    latency_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS turns_call_id_turn_index_idx ON turns(call_id, turn_index);

CREATE TABLE IF NOT EXISTS call_metrics (
    call_id TEXT PRIMARY KEY REFERENCES calls(call_id) ON DELETE CASCADE,
    avg_stt_latency_ms DOUBLE PRECISION,
    avg_llm_first_token_ms DOUBLE PRECISION,
    avg_tts_first_audio_ms DOUBLE PRECISION,
    avg_voice_to_voice_ms DOUBLE PRECISION,
    interruption_count INTEGER NOT NULL DEFAULT 0,
    agent_interrupted_user_count INTEGER NOT NULL DEFAULT 0,
    audio_drop_count INTEGER NOT NULL DEFAULT 0,
    provider_error_count INTEGER NOT NULL DEFAULT 0,
    raw_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS provider_errors (
    id BIGSERIAL PRIMARY KEY,
    call_id TEXT NOT NULL REFERENCES calls(call_id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    error_type TEXT NOT NULL,
    error_code TEXT,
    message TEXT NOT NULL,
    retryable BOOLEAN NOT NULL DEFAULT false,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS provider_errors_call_id_idx ON provider_errors(call_id);
