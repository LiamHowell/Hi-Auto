import os
import wave
from datetime import datetime

import numpy as np
import sounddevice as sd
import soundfile as sf
import openai

# TODO: Pretty sure I can remove sounddevice and soundfile

from pydub import AudioSegment
from pydub.playback import play as pydub_play

sd.default.device = (1, 1)

class AudioManager:
    def __init__(
        self,
        api_key: str = None,
        sample_rate: int = 16000,
        tts_sample_rate: int = 24000,
        channels: int = 1,
        chunk_duration: float = 1.0,
        silence_threshold: float = 400.0,
        silence_limit: int = 2,
        recorded_audio_dir: str = "recorded_audio",
        max_clips: int = 5,
    ):
        """
        Initialize AudioManager.  If api_key is provided, sets openai.api_key.
        All other args override defaults for recording, playback, file management.
        """
        if api_key:
            openai.api_key = api_key

        # store settings on self
        self.SAMPLE_RATE = sample_rate
        self.TTS_SAMPLE_RATE = tts_sample_rate
        self.CHANNELS = channels
        self.CHUNK_DURATION = chunk_duration
        self.SILENCE_THRESHOLD = silence_threshold
        self.SILENCE_LIMIT = silence_limit
        self.RECORDED_AUDIO_DIR = recorded_audio_dir
        self.MAX_CLIPS = max_clips

        os.makedirs(self.RECORDED_AUDIO_DIR, exist_ok=True)

    def _is_silence(self, audio_chunk: np.ndarray) -> bool:
        rms = np.sqrt(np.mean(np.square(audio_chunk.astype(np.float32))))
        return rms < self.SILENCE_THRESHOLD

    def _save_wav(self, audio: np.ndarray, filename: str) -> str:
        filepath = os.path.join(self.RECORDED_AUDIO_DIR, filename)
        with wave.open(filepath, "wb") as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(2)  # int16
            wf.setframerate(self.SAMPLE_RATE)
            wf.writeframes(audio.tobytes())
        return filepath

    def _maintain_max_clips(self):
        files = [
            os.path.join(self.RECORDED_AUDIO_DIR, f)
            for f in os.listdir(self.RECORDED_AUDIO_DIR)
            if f.endswith(".wav")
        ]
        files.sort(key=os.path.getmtime)
        while len(files) > self.MAX_CLIPS:
            to_delete = files.pop(0)
            os.remove(to_delete)
            print(f"Deleted old clip: {to_delete}")

    def play_audio(self, audio: np.ndarray, samplerate: int = None):
        """Play a numpy array of int16 audio via pydub."""
        samplerate = samplerate or self.SAMPLE_RATE
        # Convert numpy array to AudioSegment
        seg = AudioSegment(
            audio.tobytes(),
            frame_rate=samplerate,
            sample_width=2,
            channels=self.CHANNELS,
        )
        pydub_play(seg)

    def play_tts(self, filename: str):
        """Play a pre-rendered TTS file (wav/mp3)."""
        seg = AudioSegment.from_file(filename)
        pydub_play(seg)

    def play_funky_audio(self, filename: str, samplerate: int):
        """Play any audio file at the given samplerate."""
        seg = AudioSegment.from_file(filename)
        if samplerate and seg.frame_rate != samplerate:
            seg = seg.set_frame_rate(samplerate)
        pydub_play(seg)

    def capture_audio(self) -> (np.ndarray, str):
        """
        Record from the default mic until SILENCE_LIMIT chunks are silent in a row
        (or until Ctrl+C). Returns (full_audio_array, filepath) or (empty array, None).
        """
        sr = self.SAMPLE_RATE
        ch = self.CHANNELS
        chunk_size = int(self.CHUNK_DURATION * sr)
        silent_count = 0
        collected = []

        print("Started Recording (Ctrl+C to stop early)â¦")
        try:
            with sd.InputStream(samplerate=sr, channels=ch, dtype="int16") as stream:
                while True:
                    block, overflowed = stream.read(chunk_size)
                    if overflowed:
                        print("â  buffer overflow")
                    if ch == 1:
                        block = block.flatten()
                    collected.append(block.copy())
                    if self._is_silence(block):
                        silent_count += 1
                        print(f"Silence detected {silent_count}/{self.SILENCE_LIMIT}")
                        if silent_count >= self.SILENCE_LIMIT:
                            print("Silence threshold reached, stopping.")
                            break
                    else:
                        silent_count = 0
        except KeyboardInterrupt:
            print("\nRecording interrupted by user.")

        if not collected:
            print("No audio captured.")
            return np.array([], dtype="int16"), None

        full_audio = np.concatenate(collected, axis=0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"recording_{timestamp}.wav"
        path = self._save_wav(full_audio, filename)
        print(f"Saved: {path}")
        self._maintain_max_clips()
        return full_audio, path

    def transcribe_audio_whisper(self, filepath: str, display: bool = False):
        """
        Send the WAV at filepath to OpenAI Whisper and return (text, full_response).
        """
        try:
            with open(filepath, "rb") as f:
                resp = openai.audio.transcriptions.create(
                    model="whisper-1",
                    file=f
                )
            if display:
                print("Transcription:", resp.text)
            return resp.text, resp
        except Exception as e:
            print("Transcription error:", e)
            return None, None

