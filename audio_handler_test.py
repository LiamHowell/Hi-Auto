import secrets
from audio_manager.audio_manager import AudioManager

def main(transcribe=False):

    am = AudioManager(
        api_key=secrets.audio_openai_api_key,
        chunk_duration=1.0,
        silence_threshold=400,
        silence_limit=2,
        max_clips=5
    )

    print("Pre-record audio")
    am.play_tts("playback_audio/greeting.mp3")
    am.play_funky_audio("playback_audio/beep.wav", 44100)

    print("Recording...")
    full_audio, path = am.capture_audio()
    am.play_tts("playback_audio/captured.mp3")

    print("Playing back...")
    am.play_audio(full_audio)

    if transcribe:
        print("Transcribing…")
        am.play_tts("playback_audio/transcription_computing.mp3")

        text, _ = am.transcribe_audio_whisper(path, display=True)
    else:
        print("Not transcribing")
        am.play_tts("playback_audio/transcription_disabled.mp3")

    print("\nAll done.")
    am.play_tts("playback_audio/farewell_2.mp3")

if __name__ == "__main__":
    main()