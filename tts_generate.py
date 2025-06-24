from pathlib import Path
from openai import OpenAI

import secrets

input = "Add some text here so you can make some epic noises between audio prompts"

filename = "filename_goes_here"


# filename = input # the TTS ignores underscores so feel free to replace this line w/ above

instructions = """Identity: A robot\n\nAffect: Monotone, mechanical, and neutral, reflecting the robotic nature of the customer service agent.\n\nTone: Efficient, direct, and formal, with a focus on delivering information clearly and without emotion.\n\nEmotion: Neutral and impersonal, with no emotional inflection, as the robot voice is focused purely on functionality.\n\nPauses: very brief and purposeful.\n\nPronunciation: Clear, precise, and consistent, with each word spoken distinctly to ensure the customer can easily follow the automated process."""


client = OpenAI(api_key = secrets.audio_openai_api_key)

filename = "playback_audio/"+ filename + ".mp3"

speech_file_path = Path(__file__).parent / filename

'''
Best robot voices imo
1. onyx - robot
2. echo
3. fable

Good beep sound
hint.wav by dland -- https://freesound.org/s/320181/ -- License: Creative Commons 0

'''

with client.audio.speech.with_streaming_response.create(
    model="gpt-4o-mini-tts",
    voice="onyx",
    input=input,
    instructions=instructions,
) as response:
    response.stream_to_file(speech_file_path)