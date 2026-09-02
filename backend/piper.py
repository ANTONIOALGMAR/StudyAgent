import types
from dataclasses import dataclass

@dataclass
class _VoiceConfig:
    sample_rate: int = 16000

class PiperVoice:
    config = _VoiceConfig()

    @classmethod
    def load(cls, path: str):
        # return a lightweight voice instance
        return cls()

    def synthesize_wav(self, text: str, wav_file):
        # write a short silent WAV frame to keep interfaces happy
        # wav_file is a wave.Wave_write object
        import array
        import math
        # write 0.1s of silence
        duration = 0.1
        nframes = int(self.config.sample_rate * duration)
        frames = array.array('h', [0] * nframes)
        wav_file.writeframes(frames.tobytes())

# expose name expected by imports
PiperVoice = PiperVoice
