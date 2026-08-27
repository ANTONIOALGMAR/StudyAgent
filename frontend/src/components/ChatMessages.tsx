import type { Message } from '../hooks/useChat'

interface Props {
  messages: Message[]
  loading: boolean
  handsFree: boolean
  error: string | null
}

export default function ChatMessages({ messages, loading, handsFree, error }: Props) {
  return (
    <div className="chat-messages">
      {messages.length === 0 && (
        <div className="chat-welcome">
          <h2>Olá! 👋</h2>
          <p>Como posso ajudar nos seus estudos?</p>
          <p className="hint">🔄 modo conversa · 🖥 tela · 🎙 aperte para falar</p>
        </div>
      )}
      {messages.map((m, i) => (
        <div key={i} className={`msg msg-${m.role}`}>
          <div className="msg-role">{m.role === 'user' ? 'você' : 'study'}</div>
          <div className="msg-content">{m.content}</div>
        </div>
      ))}
      {loading && !handsFree && (
        <div className="msg msg-assistant">
          <div className="msg-content typing">pensando…</div>
        </div>
      )}
      {error && <div className="msg-error">⚠ {error}</div>}
    </div>
  )
}
