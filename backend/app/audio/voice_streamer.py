import queue
import threading
import logging
from typing import Generator, AsyncGenerator
from .text_to_speech import synthesize as tts_sync

log = logging.getLogger("audio.streaming")

class VoiceStreamer:
    """
    Gerencia o streaming de texto para áudio.
    Recebe tokens do LLM, agrupa em frases e envia para o TTS.
    """
    
    def __init__(self):
        self.audio_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._worker_thread = None

    def _sentence_splitter(self, text_stream: Generator[str, None, None]) -> Generator[str, None, None]:
        """Agrupa tokens em frases completas para evitar cortes abruptos na fala."""
        buffer = ""
        delimiters = {'.', '!', '?', '\n'}
        
        for token in text_stream:
            buffer += token
            if any(buffer.endswith(d) for d in delimiters):
                yield buffer.strip()
                buffer = ""
        
        if buffer.strip():
            yield buffer.strip()

    def stream_text_to_audio(self, text_stream: Generator[str, None, None]):
        """
        Consome o stream de texto e coloca os bytes de áudio na fila.
        """
        try:
            for sentence in self._sentence_splitter(text_stream):
                if not sentence:
                    continue
                
                log.info(f"[VOICE-STREAM] Synthesizing: {sentence[:30]}...")
                audio_bytes = tts_sync(sentence)
                self.audio_queue.put(audio_bytes)
        except Exception as e:
            log.error(f"Erro no streaming de voz: {e}")
        finally:
            self.audio_queue.put(None) # Sinal de término

    def get_next_chunk(self) -> bytes | None:
        """Retorna o próximo pedaço de áudio da fila."""
        try:
            return self.audio_queue.get(timeout=0.1)
        except queue.Empty:
            return None
