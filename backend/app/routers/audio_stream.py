from fastapi.responses import StreamingResponse
from ..audio.voice_streamer import VoiceStreamer
from ..agent.llm import chat
from ..core.model_manager import resolve

async def audio_stream_generator(messages, images=None):
    streamer = VoiceStreamer()
    
    # Inicia o chat em modo stream
    # O chat() agora retorna um gerador de tokens do Ollama
    text_stream = chat(messages, images=images, stream=True)
    
    # Criamos uma thread para alimentar o streamer com tokens do LLM
    import threading
    def feed_streamer():
        for chunk in text_stream:
            # Ollama stream retorna objetos com 'message' -> 'content'
            content = chunk.get('message', {}).get('content', '')
            streamer.stream_text_to_audio(iter([content])) # Simplificado para o exemplo
            # Nota: o streamer espera um gerador, então passamos um iterador de um único token
            # mas a lógica de frase do streamer vai acumulando.
            # Para corrigir isso, precisamos que o streamer receba o stream original.
    
    # Correção: O streamer deve consumir o stream do LLM diretamente
    def feed_streamer_fixed():
        def token_gen():
            for chunk in text_stream:
                yield chunk.get('message', {}).get('content', '')
        
        streamer.stream_text_to_audio(token_gen())

    threading.Thread(target=feed_streamer_fixed, daemon=True).start()

    # Envia chunks de áudio para o cliente conforme ficam prontos
    while True:
        chunk = streamer.get_next_chunk()
        if chunk is None:
            break
        yield chunk
