import { useCallback, useRef, useState } from 'react'
import {
  chat,
  type ChatResponse,
  type EvidenceData,
  uploadDocument,
  type UploadedDoc,
} from '../api'
import type { FaceState } from '../components/AgentFace'

export interface Message {
  role: 'user' | 'assistant'
  content: string
}

const HAPPY_WORDS = [
  'parabéns', 'parabens', 'correto', 'exato', 'isso mesmo', 'muito bem',
  'excelente', 'perfeito', 'você acertou', 'voce acertou', 'ótimo', 'otimo',
]
const CONCERN_WORDS = [
  'cuidado', 'atenção', 'atencao', 'erro', 'errado', 'incorreto',
  'não é isso', 'nao e isso', 'quase lá', 'revise', 'ops',
]

function moodFromResponse(text: string): FaceState {
  const lower = text.toLowerCase()
  const happy = HAPPY_WORDS.filter((w) => lower.includes(w)).length
  const concern = CONCERN_WORDS.filter((w) => lower.includes(w)).length
  if (concern > happy) return 'concerned'
  if (happy > concern) return 'happy'
  if (text.trim().endsWith('?')) return 'curious'
  return 'idle'
}

export interface UseChatOptions {
  useScreen: boolean
  liveOpen: boolean
  monitorSel: number
  activeDoc: UploadedDoc | null
  onMood?: (mood: FaceState) => void
}

export function useChat({ useScreen, liveOpen, monitorSel, activeDoc, onMood }: UseChatOptions) {
  const [messages, setMessages] = useState<Message[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastEvidence, setLastEvidence] = useState<EvidenceData | null>(null)
  const [lastToolsUsed, setLastToolsUsed] = useState<string[]>([])
  const monitorSelRef = useRef(monitorSel)
  const sessionIdRef = useRef(sessionId)

  monitorSelRef.current = monitorSel
  sessionIdRef.current = sessionId

  const sendText = useCallback(
    async (
      text: string,
      opts: { viaVoice?: boolean; awaitSpeech?: boolean; imageB64?: string; onSpeech?: (t: string) => Promise<void> } = {},
    ) => {
      if (!text || loading) return
      setError(null)
      setMessages((m) => [
        ...m,
        {
          role: 'user',
          content: `${opts.imageB64 ? '📷 ' : ''}${opts.viaVoice ? `🎙 ${text}` : text}`,
        },
      ])
      setLoading(true)
      try {
        const res: ChatResponse = await chat(
          text,
          sessionIdRef.current,
          useScreen || liveOpen,
          opts.imageB64 ?? null,
          monitorSelRef.current,
          activeDoc?.id ?? null,
        )
        setSessionId(res.session_id)
        sessionIdRef.current = res.session_id
        const tools = res.tools_used.length > 0 ? ` [${res.tools_used.join(', ')}]` : ''
        setMessages((m) => [...m, { role: 'assistant', content: res.response + tools }])
        setLastEvidence(res.evidence ?? null)
        setLastToolsUsed(res.tools_used)
        onMood?.(moodFromResponse(res.response))
        if (opts.onSpeech) await opts.onSpeech(res.response)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Erro desconhecido')
      } finally {
        setLoading(false)
      }
    },
    [loading, useScreen, liveOpen, activeDoc, onMood],
  )

  const loadDocument = useCallback(
    async (file: File) => {
      setError(null)
      setLoading(true)
      try {
        const doc = await uploadDocument(file)
        setMessages((m) => [
          ...m,
          {
            role: 'assistant',
            content: `📄 ${doc.name} carregado (${doc.pages} página${doc.pages > 1 ? 's' : ''}). Pergunte sobre o conteúdo!`,
          },
        ])
        return doc
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Erro ao carregar documento')
        return null
      } finally {
        setLoading(false)
      }
    },
    [],
  )

  return {
    messages, setMessages,
    sessionId, setSessionId,
    loading, setLoading,
    error, setError,
    lastEvidence, lastToolsUsed,
    sendText, loadDocument,
    sessionIdRef,
  }
}
