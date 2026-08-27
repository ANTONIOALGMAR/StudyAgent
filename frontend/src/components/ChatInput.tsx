import { useRef } from 'react'

interface Props {
  input: string
  setInput: (v: string) => void
  onSend: () => void
  onToggleRecording: () => void
  recording: boolean
  loading: boolean
  handsFree: boolean
  voiceOn: boolean
  setVoiceOn: (v: boolean) => void
  onStartHandsFree: () => void
  onStopHandsFree: () => void
  onFileChosen: (file: File) => void
}

export default function ChatInput({
  input, setInput, onSend, onToggleRecording,
  recording, loading, handsFree, voiceOn, setVoiceOn,
  onStartHandsFree, onStopHandsFree, onFileChosen,
}: Props) {
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  return (
    <div className="chat-input">
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.txt,.md"
        style={{ display: 'none' }}
        onChange={(e) => {
          const file = e.target.files?.[0]
          e.target.value = ''
          if (file) onFileChosen(file)
        }}
      />
      <button
        className={`btn-mic ${recording ? 'recording' : ''}`}
        onClick={onToggleRecording}
        disabled={loading || handsFree}
        title={recording ? 'Parar gravação e enviar' : 'Falar com o agente (aperte para falar)'}
      >
        🎙
      </button>
      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && onSend()}
        placeholder={handsFree ? 'modo conversa ativo — pode falar!' : 'Fale com o StudyAgent…'}
        disabled={loading || recording}
      />
      <button
        className={`btn-screen ${voiceOn ? 'active' : ''}`}
        onClick={() => setVoiceOn(!voiceOn)}
        title="Responder por voz"
      >
        🔊
      </button>
      <button
        className={`btn-send ${handsFree ? 'hf-on' : ''}`}
        onClick={() => (handsFree ? onStopHandsFree() : onStartHandsFree())}
        title={handsFree ? 'Desligar modo conversa' : 'Modo conversa automática'}
      >
        {handsFree ? '⏹' : '🔄'}
      </button>
    </div>
  )
}
