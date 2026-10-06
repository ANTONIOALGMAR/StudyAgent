import { useCallback, useRef, useState } from 'react'
import {
  answerScreenQuestions,
  chat,
  type ChatResponse,
  type EvidenceData,
  uploadDocument,
  type UploadedDoc,
} from '../api'
import type { Agent3DState as FaceState } from '../components/StudyAgent3D/agentStates'

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
const EXCITED_WORDS = [
  'uau', 'incrível', 'incrivel', 'genial', 'maravilhoso', 'fantástico', 'fantastico',
  'adorei', 'parabéns de novo', 'show de bola', 'demais!',
]
const CONFUSED_WORDS = [
  'não sei', 'nao sei', 'não tenho certeza', 'nao tenho certeza', 'não entendi',
  'nao entendi', 'não entendi sua pergunta', 'não ficou claro', 'nao ficou claro',
]

function moodFromResponse(text: string): FaceState {
  const lower = text.toLowerCase()
  const happy = HAPPY_WORDS.filter((w) => lower.includes(w)).length
  const concern = CONCERN_WORDS.filter((w) => lower.includes(w)).length
  if (EXCITED_WORDS.some((w) => lower.includes(w))) return 'excited'
  if (CONFUSED_WORDS.some((w) => lower.includes(w))) return 'confused'
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
  const useScreenRef = useRef(useScreen)
  const liveOpenRef = useRef(liveOpen)

  monitorSelRef.current = monitorSel
  sessionIdRef.current = sessionId
  useScreenRef.current = useScreen
  liveOpenRef.current = liveOpen

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
          useScreenRef.current || liveOpenRef.current,
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
    [loading, activeDoc, onMood],
  )

  const loadDocument = useCallback(
    async (file: File) => {
      setError(null)
      setLoading(true)
      try {
        const doc = await uploadDocument(file)
        const isImage = doc.kind === 'image'
        const aviso = isImage
          ? `🖼️ ${doc.name} carregado. Mande "resolva as questões" que eu leio a imagem.`
          : `📄 ${doc.name} carregado (${doc.pages} página${doc.pages > 1 ? 's' : ''}). Pergunte sobre o conteúdo!`
        setMessages((m) => [...m, { role: 'assistant', content: aviso }])
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

  const solveScreenQuestions = useCallback(
    async (monitor?: number | null) => {
      setError(null)
      setLoading(true)
      setMessages((m) => [
        ...m,
        { role: 'user', content: '🧩 Resolva as questões da tela sob comando' },
      ])
      try {
        const res = await answerScreenQuestions(monitor ?? null, null, sessionIdRef.current)
        if (res.session_id) {
          setSessionId(res.session_id)
          sessionIdRef.current = res.session_id
        }
        const tela = res.screen_detected
          ? `tela ${(res.monitor ?? 0) + 1}${res.monitor_name ? ` (${res.monitor_name})` : ''}`
          : 'tela não identificada'
        let content = res.answer_text
        if (res.questions.length === 0) {
          content = `Não encontrei questões numeradas na ${tela}. Aproxime a lista ou troque de tela.`
        } else {
          const cabecalho = `📺 ${tela} · ${res.questions.length} questão(ões) — ${res.screen_detected ? 'tela sob comando' : 'tela padrão'}`
          content = `${cabecalho}\n\n${res.answer_text}`
        }
        setMessages((m) => [...m, { role: 'assistant', content }])
        onMood?.(moodFromResponse(res.answer_text))
        return res
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Erro ao ler as questões')
        return null
      } finally {
        setLoading(false)
      }
    },
    [onMood],
  )

  return {
    messages, setMessages,
    sessionId, setSessionId,
    loading, setLoading,
    error, setError,
    lastEvidence, lastToolsUsed,
    sendText, loadDocument, solveScreenQuestions,
    sessionIdRef,
    setUseScreen: (v: boolean) => { useScreenRef.current = v },
    setLiveOpen: (v: boolean) => { liveOpenRef.current = v },
    setMonitorSel: (v: number) => { monitorSelRef.current = v },
  }
}
