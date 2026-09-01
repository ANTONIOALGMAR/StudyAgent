from ..audio.voice_streamer import VoiceStreamer
from ..agent.llm import chat

async def audio_stream_generator(messages, images=None):
    streamer = VoiceStreamer()

    # O chat() retorna um gerador de tokens do Ollama em modo stream.
    text_stream = chat(messages, images=images, stream=True)

    # Thread consome o stream do LLM e alimenta o streamer de áudio.
    def feed():
        def token_gen():
            for chunk in text_stream:
                yield chunk.get('message', {}).get('content', '')

        streamer.stream_text_to_audio(token_gen())

    import threading
    threading.Thread(target=feed, daemon=True).start()

    # Envia chunks de áudio para o cliente conforme ficam prontos.
    while True:
        chunk = streamer.get_next_chunk()
        if chunk is None:
            break
        yield chunk