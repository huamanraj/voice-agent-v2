"""Local Silero VAD and Smart Turn v3 ONNX runtimes."""

import asyncio
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from voice_agent.config import Settings
from voice_agent.contracts.audio import AudioFrame
from voice_agent.contracts.events import SpeechStart, SpeechStop
from voice_agent.core.turn_detection.smart_turn_runner import SmartTurnDecision

MODEL_SAMPLE_RATE = 16000
SILERO_WINDOW_SAMPLES = 512
SILERO_CONTEXT_SAMPLES = 64
SMART_TURN_MAX_SECONDS = 8


@dataclass(slots=True)
class TurnDetectionModels:
    vad: "SileroVADModel | None"
    smart_turn: "SmartTurnV3Model | None"

    @property
    def ready(self) -> bool:
        return self.vad is not None and self.smart_turn is not None


async def preload_turn_detection_models(settings: Settings) -> TurnDetectionModels:
    """Load model sessions outside the request/call path."""

    return await asyncio.to_thread(TurnDetectionModelsLoader(settings).load)


class TurnDetectionModelsLoader:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def load(self) -> TurnDetectionModels:
        vad = SileroVADModel(self.settings.vad_model_path) if self.settings.vad_enabled else None
        smart_turn = (
            SmartTurnV3Model(
                self.settings.smart_turn_model_path,
                cpu_count=self.settings.smart_turn_cpu_threads,
            )
            if self.settings.smart_turn_enabled
            else None
        )
        return TurnDetectionModels(vad=vad, smart_turn=smart_turn)


class SileroVADModel:
    """Thread-safe ONNX session holder; per-call state lives in SileroVADStream."""

    def __init__(self, model_path: str) -> None:
        path = _existing_file(model_path, "Silero VAD")
        ort = _import_onnxruntime()
        options = ort.SessionOptions()
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.inter_op_num_threads = 1
        options.intra_op_num_threads = 1
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        providers = (
            ["CPUExecutionProvider"]
            if "CPUExecutionProvider" in ort.get_available_providers()
            else None
        )
        self.session = ort.InferenceSession(str(path), sess_options=options, providers=providers)

    def create_stream(self, call_id: str, settings: Settings) -> "SileroVADStream":
        return SileroVADStream(
            call_id=call_id,
            session=self.session,
            confidence_threshold=settings.vad_confidence_threshold,
            start_min_ms=settings.vad_start_min_ms,
            stop_min_ms=settings.vad_stop_min_ms,
        )


class SileroVADStream:
    def __init__(
        self,
        *,
        call_id: str,
        session: Any,
        confidence_threshold: float,
        start_min_ms: int,
        stop_min_ms: int,
    ) -> None:
        self.call_id = call_id
        self.session = session
        self.confidence_threshold = confidence_threshold
        self.negative_threshold = max(confidence_threshold - 0.15, 0.01)
        self.start_min_ms = start_min_ms
        self.stop_min_ms = stop_min_ms
        self._np = _import_numpy()
        self._pending = self._np.zeros(0, dtype=self._np.float32)
        self._base_timestamp_ms: int | None = None
        self._processed_samples = 0
        self._speech_candidate_start_ms: int | None = None
        self._silence_candidate_start_ms: int | None = None
        self._last_speech_confidence = 0.0
        self._triggered = False
        self.reset_model_state()

    def reset_model_state(self) -> None:
        self._state = self._np.zeros((2, 1, 128), dtype=self._np.float32)
        self._context = self._np.zeros((1, SILERO_CONTEXT_SAMPLES), dtype=self._np.float32)

    def process_frame(self, frame: AudioFrame) -> list[SpeechStart | SpeechStop]:
        if frame.codec != "pcm16_16k" or frame.sample_rate != MODEL_SAMPLE_RATE:
            raise ValueError("Silero VAD requires PCM16 16k mono audio frames.")
        if frame.channels != 1:
            raise ValueError("Silero VAD requires mono audio.")
        if self._base_timestamp_ms is None:
            self._base_timestamp_ms = frame.timestamp_ms

        samples = _pcm16_bytes_to_float32(frame.data, self._np)
        if samples.size == 0:
            return []

        self._pending = self._np.concatenate((self._pending, samples))
        events: list[SpeechStart | SpeechStop] = []
        while self._pending.size >= SILERO_WINDOW_SAMPLES:
            chunk = self._pending[:SILERO_WINDOW_SAMPLES]
            self._pending = self._pending[SILERO_WINDOW_SAMPLES:]
            start_ms = self._sample_to_ms(self._processed_samples)
            self._processed_samples += SILERO_WINDOW_SAMPLES
            end_ms = self._sample_to_ms(self._processed_samples)
            probability = self._speech_probability(chunk)
            event = self._event_from_probability(probability, start_ms, end_ms)
            if event is not None:
                events.append(event)
        return events

    def flush(self) -> SpeechStop | None:
        if not self._triggered:
            return None
        stop_ms = self._sample_to_ms(self._processed_samples)
        self._triggered = False
        self._speech_candidate_start_ms = None
        self._silence_candidate_start_ms = None
        self.reset_model_state()
        return SpeechStop(
            call_id=self.call_id,
            ts_ms=stop_ms,
            source="vad",
            confidence=self._last_speech_confidence,
        )

    def _speech_probability(self, chunk: Any) -> float:
        chunk = chunk.reshape(1, SILERO_WINDOW_SAMPLES)
        model_input = self._np.concatenate((self._context, chunk), axis=1)
        outputs = self.session.run(
            None,
            {
                "input": model_input.astype(self._np.float32),
                "state": self._state,
                "sr": self._np.array(MODEL_SAMPLE_RATE, dtype=self._np.int64),
            },
        )
        probability, state = outputs
        self._state = state
        self._context = model_input[:, -SILERO_CONTEXT_SAMPLES:]
        return float(probability.reshape(-1)[0])

    def _event_from_probability(
        self,
        probability: float,
        start_ms: int,
        end_ms: int,
    ) -> SpeechStart | SpeechStop | None:
        if probability >= self.confidence_threshold:
            self._last_speech_confidence = max(self._last_speech_confidence, probability)
            self._silence_candidate_start_ms = None
            if self._speech_candidate_start_ms is None:
                self._speech_candidate_start_ms = start_ms
            if (
                not self._triggered
                and end_ms - self._speech_candidate_start_ms >= self.start_min_ms
            ):
                self._triggered = True
                return SpeechStart(
                    call_id=self.call_id,
                    ts_ms=self._speech_candidate_start_ms,
                    source="vad",
                    confidence=self._last_speech_confidence,
                )
            return None

        self._speech_candidate_start_ms = None
        if self._triggered and probability < self.negative_threshold:
            if self._silence_candidate_start_ms is None:
                self._silence_candidate_start_ms = start_ms
            if end_ms - self._silence_candidate_start_ms >= self.stop_min_ms:
                stop_ms = self._silence_candidate_start_ms
                confidence = self._last_speech_confidence
                self._triggered = False
                self._silence_candidate_start_ms = None
                self._last_speech_confidence = 0.0
                self.reset_model_state()
                return SpeechStop(
                    call_id=self.call_id,
                    ts_ms=stop_ms,
                    source="vad",
                    confidence=confidence,
                )
        return None

    def _sample_to_ms(self, sample_index: int) -> int:
        base = self._base_timestamp_ms or 0
        return base + round(sample_index * 1000 / MODEL_SAMPLE_RATE)


class SmartTurnV3Model:
    """Local Smart Turn v3 ONNX inference over PCM16/16k turn audio."""

    def __init__(self, model_path: str, *, cpu_count: int = 1) -> None:
        path = _existing_file(model_path, "Smart Turn v3")
        np = _import_numpy()
        ort = _import_onnxruntime()
        feature_extractor_cls = _import_whisper_feature_extractor()

        options = ort.SessionOptions()
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.inter_op_num_threads = 1
        options.intra_op_num_threads = max(1, cpu_count)
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        self._np = np
        self._feature_extractor = feature_extractor_cls(chunk_length=SMART_TURN_MAX_SECONDS)
        self._session = ort.InferenceSession(str(path), sess_options=options)

    def classify(self, frame: AudioFrame) -> SmartTurnDecision:
        if frame.codec != "pcm16_16k" or frame.sample_rate != MODEL_SAMPLE_RATE:
            raise ValueError("Smart Turn v3 requires PCM16 16k mono audio.")
        audio = _pcm16_bytes_to_float32(frame.data, self._np)
        audio = _last_or_left_padded(audio, SMART_TURN_MAX_SECONDS * MODEL_SAMPLE_RATE, self._np)
        inputs = self._feature_extractor(
            audio,
            sampling_rate=MODEL_SAMPLE_RATE,
            return_tensors="np",
            padding="max_length",
            max_length=SMART_TURN_MAX_SECONDS * MODEL_SAMPLE_RATE,
            truncation=True,
            do_normalize=True,
        )
        input_features = inputs.input_features.squeeze(0).astype(self._np.float32)
        input_features = self._np.expand_dims(input_features, axis=0)
        outputs = self._session.run(None, {"input_features": input_features})
        probability = float(outputs[0][0].item())
        return SmartTurnDecision(
            is_complete=probability > 0.5,
            confidence=probability,
            reason="smart_turn_v3_onnx",
        )


def _existing_file(path: str, label: str) -> Path:
    model_path = Path(path).expanduser()
    if not model_path.is_absolute():
        model_path = Path.cwd() / model_path
    if not model_path.is_file():
        raise FileNotFoundError(
            f"{label} model file not found at {model_path}. "
            "Run scripts/download_models.py or set the matching *_MODEL_PATH env var."
        )
    return model_path


def _pcm16_bytes_to_float32(data: bytes, np: Any) -> Any:
    if len(data) % 2 != 0:
        raise ValueError("PCM16 audio length must be even.")
    samples = array("h")
    samples.frombytes(data)
    return np.asarray(samples, dtype=np.float32) / 32768.0


def _last_or_left_padded(audio: Any, max_samples: int, np: Any) -> Any:
    if audio.size > max_samples:
        return audio[-max_samples:]
    if audio.size < max_samples:
        return np.pad(audio, (max_samples - audio.size, 0), mode="constant")
    return audio


def _import_numpy() -> Any:
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("numpy is required for local VAD and Smart Turn inference.") from exc
    return np


def _import_onnxruntime() -> Any:
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise RuntimeError("onnxruntime is required for local VAD and Smart Turn inference.") from exc
    return ort


def _import_whisper_feature_extractor() -> Any:
    try:
        from transformers import WhisperFeatureExtractor
    except ImportError as exc:
        raise RuntimeError("transformers is required for Smart Turn v3 feature extraction.") from exc
    return WhisperFeatureExtractor
