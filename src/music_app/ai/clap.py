from __future__ import annotations

import math
import subprocess
import tempfile
import wave
from collections.abc import Sequence
from pathlib import Path

from music_app.domain import AIEnrichment

DEFAULT_GENRES = (
    "hip-hop",
    "rap",
    "rock",
    "pop",
    "electronic",
    "house",
    "techno",
    "metal",
    "jazz",
    "classical",
    "country",
    "r&b",
    "soul",
    "reggae",
    "folk",
    "ambient",
)
DEFAULT_MOODS = (
    "energetic",
    "chill",
    "dark",
    "uplifting",
    "aggressive",
    "melancholic",
    "romantic",
    "dreamy",
)


def rank_labels(
    similarities: Sequence[float], labels: Sequence[str], threshold: float
) -> list[tuple[str, float]]:
    if len(similarities) != len(labels):
        raise ValueError("similarities and labels must have the same length")
    if not labels:
        return []
    max_value = max(float(value) for value in similarities)
    exps = [math.exp(float(value) - max_value) for value in similarities]
    total = sum(exps)
    probabilities = [value / total for value in exps]
    ranked = [
        (label, probability)
        for label, probability in zip(labels, probabilities, strict=True)
        if probability >= threshold
    ]
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked


class CLAPAnalyzer:
    def __init__(
        self,
        model_name: str = "laion/clap-htsat-unfused",
        *,
        threshold: float = 0.18,
        excerpt_seconds: int = 45,
    ) -> None:
        self.model_name = model_name
        self.threshold = threshold
        self.excerpt_seconds = excerpt_seconds
        self._model = None
        self._processor = None

    def analyze(self, path: Path) -> AIEnrichment:
        try:
            import numpy as np
            import torch
            from transformers import ClapModel, ClapProcessor
        except ImportError as exc:
            return AIEnrichment(
                available=False,
                error=f"Local AI dependencies are not installed: {exc.name or exc}",
            )

        try:
            processor, model = self._load_model(ClapProcessor, ClapModel)
            samples = self._decode_excerpt(Path(path), np)
            genres = self._score_group(samples, DEFAULT_GENRES, processor, model, torch)
            moods = self._score_group(samples, DEFAULT_MOODS, processor, model, torch)
            return AIEnrichment(genres=tuple(genres), moods=tuple(moods), available=True)
        except FileNotFoundError as exc:
            return AIEnrichment(available=False, error=f"Required local tool was not found: {exc}")
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
            return AIEnrichment(available=False, error=f"Local AI analysis failed: {exc}")

    def _load_model(self, processor_cls, model_cls):
        if self._processor is None:
            self._processor = processor_cls.from_pretrained(self.model_name)
        if self._model is None:
            self._model = model_cls.from_pretrained(self.model_name)
            self._model.eval()
        return self._processor, self._model

    def _decode_excerpt(self, path: Path, np):
        with tempfile.TemporaryDirectory(prefix="music-ai-") as temp_dir:
            wav_path = Path(temp_dir) / "excerpt.wav"
            completed = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    str(path),
                    "-t",
                    str(self.excerpt_seconds),
                    "-ac",
                    "1",
                    "-ar",
                    "48000",
                    "-c:a",
                    "pcm_s16le",
                    str(wav_path),
                ],
                capture_output=True,
                text=True,
                timeout=max(60, self.excerpt_seconds * 2),
                check=False,
            )
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout or "ffmpeg failed").strip()
                raise RuntimeError(detail)
            with wave.open(str(wav_path), "rb") as handle:
                if handle.getnchannels() != 1 or handle.getframerate() != 48000:
                    raise ValueError("decoded audio is not mono 48 kHz PCM")
                pcm = handle.readframes(handle.getnframes())
            return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0

    def _score_group(self, samples, labels, processor, model, torch):
        prompts = [f"A music track that sounds {label}" for label in labels]
        audio_inputs = processor(
            audios=samples,
            sampling_rate=48000,
            return_tensors="pt",
        )
        text_inputs = processor(text=prompts, padding=True, return_tensors="pt")
        with torch.no_grad():
            audio_features = model.get_audio_features(**audio_inputs)
            text_features = model.get_text_features(**text_inputs)
            audio_features = audio_features / audio_features.norm(dim=-1, keepdim=True)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            similarities = (audio_features @ text_features.T).squeeze(0).cpu().tolist()
        return rank_labels(similarities, labels, self.threshold)
