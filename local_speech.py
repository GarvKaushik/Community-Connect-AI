from __future__ import annotations

import asyncio
import io
import os
import re
import shutil
import uuid
from pathlib import Path

import av
import numpy as np
from faster_whisper import WhisperModel
from livekit import rtc
from livekit.agents import DEFAULT_API_CONNECT_OPTIONS, APIConnectOptions, NOT_GIVEN, stt, tts
from piper import PiperVoice, SynthesisConfig

PIPER_DIR = Path(__file__).with_name("models") / "piper"
PIPER_VOICES = {
    "en": ("en/en_US/lessac/medium", "en_US-lessac-medium"),
    "hi": ("hi/hi_IN/pratham/medium", "hi_IN-pratham-medium"),
}
_UNSPOKEN = re.compile(r"\([^)]*\)|\[[^\]]*\]|[*#_`]")


def load_piper_voices() -> dict[str, PiperVoice]:
    """Load one Piper voice per language, downloading any that are missing."""
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    from huggingface_hub import hf_hub_download

    voices = {}
    for language, (folder, name) in PIPER_VOICES.items():
        model_path = PIPER_DIR / f"{name}.onnx"
        if not model_path.exists():
            for suffix in (".onnx", ".onnx.json"):
                hf_hub_download(
                    "rhasspy/piper-voices", f"{folder}/{name}{suffix}", local_dir=PIPER_DIR / "_hf"
                )
                (PIPER_DIR / "_hf" / folder / f"{name}{suffix}").replace(PIPER_DIR / f"{name}{suffix}")
            shutil.rmtree(PIPER_DIR / "_hf", ignore_errors=True)
        voices[language] = PiperVoice.load(str(model_path))
    return voices


class FasterWhisperSTT(stt.STT):
    """Local Whisper transcription in the language the user chose before starting.

    A fixed language is more accurate than per-turn detection, which often confuses Hindi
    with Urdu, and faster, since detection costs a second full encoder pass.
    """

    def __init__(self, model: WhisperModel, language: str) -> None:
        super().__init__(
            capabilities=stt.STTCapabilities(streaming=False, interim_results=False)
        )
        self._model = model
        self._language = language

    @property
    def model(self) -> str:
        return "faster-whisper"

    @property
    def provider(self) -> str:
        return "local"

    async def _recognize_impl(
        self,
        buffer: stt.AudioBuffer,
        *,
        language: str = NOT_GIVEN,
        conn_options: APIConnectOptions,
    ) -> stt.SpeechEvent:
        transcript = await asyncio.to_thread(self._transcribe, buffer)
        return stt.SpeechEvent(
            type=stt.SpeechEventType.FINAL_TRANSCRIPT,
            request_id=str(uuid.uuid4()),
            alternatives=[stt.SpeechData(text=transcript, language=self._language)],
        )

    def _transcribe(self, buffer: stt.AudioBuffer) -> str:
        wav_bytes = rtc.combine_audio_frames(buffer).to_wav_bytes()
        container = av.open(io.BytesIO(wav_bytes))
        resampler = av.AudioResampler(format="flt", layout="mono", rate=16_000)
        samples: list[np.ndarray] = []
        try:
            for frame in container.decode(audio=0):
                samples.extend(
                    resampled.to_ndarray().reshape(-1)
                    for resampled in resampler.resample(frame)
                )
        finally:
            container.close()

        audio = np.concatenate(samples) if samples else np.empty(0, dtype=np.float32)
        segments, _ = self._model.transcribe(
            audio,
            language=self._language,
            beam_size=1,
            vad_filter=False,
            condition_on_previous_text=False,
        )
        return "".join(segment.text for segment in segments).strip()


class PiperTTS(tts.TTS):
    def __init__(self, voice: PiperVoice, speed: float = 1.0) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=voice.config.sample_rate,
            num_channels=1,
        )
        self._voice = voice
        self._speed = speed

    @property
    def model(self) -> str:
        return "piper"

    @property
    def provider(self) -> str:
        return "local"

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> tts.ChunkedStream:
        return _PiperChunkedStream(tts=self, input_text=text, conn_options=conn_options)

    def _synthesize(self, text: str) -> bytes:
        # The LLM sometimes adds bracketed asides or markdown; never read those aloud.
        text = _UNSPOKEN.sub("", text).strip()
        if not text:
            return b""
        config = SynthesisConfig(length_scale=1 / self._speed)
        pcm_chunks = []
        for chunk in self._voice.synthesize(text, syn_config=config):
            pcm_chunks.append(
                (np.clip(chunk.audio_float_array, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
            )
        return b"".join(pcm_chunks)


class _PiperChunkedStream(tts.ChunkedStream):
    def __init__(
        self,
        *,
        tts: PiperTTS,
        input_text: str,
        conn_options: APIConnectOptions,
    ) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._piper_tts = tts

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        pcm = await asyncio.to_thread(self._piper_tts._synthesize, self.input_text)
        output_emitter.initialize(
            request_id=str(uuid.uuid4()),
            sample_rate=self._piper_tts.sample_rate,
            num_channels=1,
            mime_type="audio/pcm",
        )
        output_emitter.push(pcm)
        output_emitter.flush()
