import asyncio
import re
import serial_asyncio
import time

class ModemProtocol(asyncio.Protocol):
    def __init__(self, handlers):
        """
        handlers: dict mapping phone_number string -> coroutine or function taking two args:
                  the protocol instance and the caller number.
        e.g. handlers["+15551234567"] = on_call_from_5551234567
        """
        self.transport = None
        self._buf = ""
        self.handlers = handlers

    def connection_made(self, transport):
        self.transport = transport
        print("Serial port opened:", transport)
        # basic modem setup
        self._at("ATE0")        # turn off echo
        self._at("AT+CLIP=1")   # enable caller-ID

    def data_received(self, data):
        text = data.decode(errors="ignore")
        self._buf += text
        lines = self._buf.split("\r\n")
        # keep incomplete last line in buffer
        self._buf = lines.pop()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            print("<<", line)
            self._handle_line(line)

    def _at(self, cmd):
        """Send an AT command, appending CR"""
        full = cmd.strip() + "\r\n"
        print(">>", cmd)
        self.transport.write(full.encode())

    def _handle_line(self, line):
        # ignore pure RING notifications if you like
        if line == "RING":
            return

        # match +CLCC unsolicited result
        m = re.match(
            r'^\+CLCC:\s*'                         # prefix
            r'(?P<idx>\d+),'                       # <idx>
            r'(?P<dir>[01]),'                      # <dir> 0=MO,1=MT
            r'(?P<stat>\d),'                       # <stat> 0..5
            r'(?P<mode>\d),'                       # <mode>
            r'(?P<mpty>\d),'                       # <mpty>
            r'"(?P<number>[^"]+)",'                # "<number>"
            r'(?P<type>\d+)'                       # <type>
            r'.*$',                                # any trailing junk
            line
        )
        if m:
            stat   = int(m.group('stat'))
            caller = m.group('number')
            # stat 0 = active, 4 = incoming, 5 = waiting
            if stat in (4, 5):
                print(f"Incoming call (stat={stat}) from {caller}")
                handler = self.handlers.get(caller)
                if handler:
                    result = handler(self, caller)
                    if asyncio.iscoroutine(result):
                        asyncio.create_task(result)
                else:
                    print(f"No handler for {caller}, hanging up")
                    time.sleep(0.5)
                    #self._at("AT+CVHU=0")
                    
                    self._at("AT+CHUP")
            elif stat == 6:
                print(f"End of call status {stat} for {caller}")
            else:
                # you can handle other call?states here if desired
                print(f"Call status {stat} for {caller}, ignoring")
            return

        # fall back to other parsing (OK, ERROR, echo, ?)
        # print("Unmatched line:", line)

# Example handlers

def default_handler(modem: ModemProtocol, caller):
    """
    Regular function handler: answer, wait 10s, hang up.
    """
    modem._at("ATA")
    print("Answered call from", caller)
    async def _later():
        await asyncio.sleep(10)
        print("Hanging up call from", caller)
        modem._at("ATH")
    return _later()

import secrets_proj
from audio_manager.audio_manager import AudioManager

async def special_handler(modem: ModemProtocol, caller):
    """
    Async function handler: answer, do async work, hang up.
    """
    transcribe = False
    modem._at("ATA")
    print("Special handler answered call from", caller)
    # simulate async work
    await asyncio.sleep(0.1)
    
    am = AudioManager(
        api_key=secrets_proj.audio_openai_api_key,
        chunk_duration=1.0,
        silence_threshold=400,
        silence_limit=2,
        max_clips=20,
        tts_sample_rate= 44100, # Adjusted to what this silly audio card wants
        sample_rate= 44100, # Still havent got this working?
        
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
        print("Transcribingâ¦")
        am.play_tts("playback_audio/transcription_computing.mp3")

        text, _ = am.transcribe_audio_whisper(path, display=True)
    else:
        print("Not transcribing")
        am.play_tts("playback_audio/transcription_disabled.mp3")

    print("\nAll done.")
    am.play_tts("playback_audio/farewell_2.mp3")
    
    print("Special handler done with", caller, "? hanging up")
    modem._at("AT+CHUP")

def main():
    # Map incoming numbers to handler functions
    handlers = {
        "+123456": default_handler,
        "my_phone_number": special_handler,
        "04_123456": special_handler, # A second phone num with the same handler
        # any number not listed here will be hung up on
    }

    loop = asyncio.get_event_loop()
    coro = serial_asyncio.create_serial_connection(
        loop,
        lambda: ModemProtocol(handlers),
        # adjust the port name to match your system:
        # e.g. "COM3" on Windows or "/dev/ttyUSB2" on Linux
        "/dev/ttyS0",
        baudrate=115200
    )
    loop.run_until_complete(coro)
    print("Event loop running. Waiting for incoming calls ?")
    loop.run_forever()

if __name__ == "__main__":
    main()
