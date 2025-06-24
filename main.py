import sounddevice as sd
import soundfile as sf
import numpy as np
import openai
import wave
import os
from datetime import datetime

import secrets

# Set your OpenAI API key
openai.api_key = secrets.audio_openai_api_key

# Audio settings
SAMPLE_RATE = 16000
TTS_SAMPLE_RATE = 24000
CHANNELS = 1
CHUNK_DURATION = 1  # seconds per chunk
SILENCE_THRESHOLD = 400  # Adjust as needed
SILENCE_LIMIT = 2  # Number of consecutive silent chunks to trigger stop
RECORDED_AUDIO_DIR = "recorded_audio"
MAX_CLIPS = 5

# GPT Generated funcs
def is_silence(audio, threshold=SILENCE_THRESHOLD):
    rms = np.sqrt(np.mean(np.square(audio.astype(np.float32))))
    return rms < threshold

def save_wav(audio, filename):
    os.makedirs(RECORDED_AUDIO_DIR, exist_ok=True)
    filepath = os.path.join(RECORDED_AUDIO_DIR, filename)
    with wave.open(filepath, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())
    return filepath

def maintain_max_clips(directory, max_clips):
    files = [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith('.wav')]
    files.sort(key=os.path.getmtime)  # Oldest first
    while len(files) > max_clips:
        os.remove(files[0])
        print(f"Deleted old clip: {files[0]}")
        files.pop(0)

def transcribe_audio_whisper(filepath, display=False):

    try:
        with open(filepath, "rb") as f:
            transcript = openai.audio.transcriptions.create(
                model="whisper-1",
                file=f
            )
        if display:
            print("Transcription:", transcript.text)
        return transcript.text, transcript
    except Exception as e:
        print("Transcription error:", e)


def play_audio(audio, samplerate=SAMPLE_RATE):
    sd.play(audio, samplerate)
    sd.wait()

# Wrappers

def play_funky_audio(filename, samplerate):
    data, _ = sf.read(filename)
    play_audio(data, samplerate)

def play_tts(filename):
    data, _ = sf.read(filename)
    print(TTS_SAMPLE_RATE)
    play_audio(data, TTS_SAMPLE_RATE)

def capture_audio():
    silence_counter = 0
    all_audio = []
    CHUNK_SAMPLES = int(CHUNK_DURATION * SAMPLE_RATE)

    print("Started Recording - (Ctrl+C to stop early)")

    try:
        # Open the stream once
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype='int16'
        ) as stream:
            while True:
                # read exactly CHUNK_SAMPLES frames
                audio_chunk, overflowed = stream.read(CHUNK_SAMPLES)
                # audio_chunk shape is (CHUNK_SAMPLES, CHANNELS)
                # squeeze down to 1D if CHANNELS==1
                if CHANNELS == 1:
                    audio_chunk = np.squeeze(audio_chunk, axis=1)
                all_audio.append(audio_chunk.copy())

                if overflowed:
                    print("Warning: buffer overflow detected")

                if is_silence(audio_chunk):
                    silence_counter += 1
                    print(f"Silence detected ({silence_counter}/{SILENCE_LIMIT})")
                    if silence_counter >= SILENCE_LIMIT:
                        print("Silence threshold reached. Stopping recording.")
                        break
                else:
                    silence_counter = 0

    except KeyboardInterrupt:
        print("\nKeyboard interrupt received. Stopping recording.")

    if not all_audio:
        print("No audio captured.")
        return np.array([], dtype='int16'), None

    # Concatenate all the chunks
    full_audio = np.concatenate(all_audio, axis=0)

    # Save to WAV
    print("\nSaving audio clip...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"recording_{timestamp}.wav"
    path = save_wav(full_audio, filename)
    print(f"Saved: {path}")

    # Enforce max clips
    maintain_max_clips(RECORDED_AUDIO_DIR, MAX_CLIPS)

    return full_audio, path


transcribe = False


def main():

    print("Pre-record audio")
    play_tts("playback_audio/greeting.mp3")
    play_funky_audio("playback_audio/beep.wav", 44100)

    print("Recording...")
    full_audio, path = capture_audio()
    play_tts("playback_audio/captured.mp3")

    print("Playing back...")
    play_audio(full_audio)

    if transcribe:
        print("Transcribing...")
        play_tts("playback_audio/transcription_computing.mp3")
        text, _ = transcribe_audio_whisper(path, display=True)
    else:
        print("Not transcribing")
        play_tts("playback_audio/transcription_disabled.mp3")

    print("\nAll done.")
    play_tts("playback_audio/farewell_2.mp3")

if __name__ == "__main__":
    main()