import { useCallback, useEffect, useRef, useState } from 'react'
import {
  answerScreenQuestions,
  captureScreen,
  detectScreenQuestions,
  getMonitors,
  screenPreviewUrl,
  chat,
  type MonitorInfo,
} from '../api'

export interface UseScreenOptions {
  sessionIdRef: React.MutableRefObject<string | null>
  setMessages: React.Dispatch<React.SetStateAction<{ role: 'user' | 'assistant'; content: string }[]>>
  setSessionId: (id: string) => void
}

// Intervalo do loop que varre a tela atrás de questões novas. OCR puro
// (sem modelo), então dá para ser perto que o custo é baixo.
const DETECT_INTERVAL_MS = 5000

export function useScreen({ sessionIdRef, setMessages, setSessionId }: UseScreenOptions) {
  const [useScreenCapture, setUseScreenCapture] = useState(false)
  const [liveOpen, setLiveOpen] = useState(false)
  const [liveMinimized, setLiveMinimized] = useState(false)
  const [watchMode, setWatchMode] = useState(false)
  const [autoSolve, setAutoSolve] = useState(false)
  const [monitors, setMonitors] = useState<MonitorInfo[]>([])
  const [monitorSel, setMonitorSel] = useState(0)
  const [previewTick, setPreviewTick] = useState(0)
  const watchActiveRef = useRef(false)
  const autoActiveRef = useRef(false)
  const monitorSelRef = useRef(0)
  const liveOpenRef = useRef(false)
  const watchAbortRef = useRef<AbortController | null>(null)
  const autoAbortRef = useRef<AbortController | null>(null)
  // Questões já resolvidas nesta rodada (fingerprint → vista). Evita reagir
  // à mesma questão que continuou na tela entre varreduras.
  const seenQuestionsRef = useRef<Set<string>>(new Set())

  useEffect(() => { monitorSelRef.current = monitorSel }, [monitorSel])
  useEffect(() => { liveOpenRef.current = liveOpen }, [liveOpen])

  // Poll dos monitores + preview ao vivo. `getMonitors` é abortado no cleanup
  // (evita rejeição não tratada quando o painel fecha durante o fetch) e o
  // preview pausa em aba oculta — 2s de JPEG a cada 2s com o Chrome em
  // background consome CPU à toa.
  useEffect(() => {
    if (!liveOpen) return
    const controller = new AbortController()
    let timer: ReturnType<typeof setInterval> | undefined
    let hidden = document.hidden

    const onVisibility = () => {
      hidden = document.hidden
      if (!hidden && !timer) startPreview()
      if (hidden && timer) { clearInterval(timer); timer = undefined }
    }

    const startPreview = () => {
      if (timer || hidden) return
      timer = setInterval(() => setPreviewTick((x) => x + 1), 2000)
    }

    getMonitors(controller.signal)
      .then(setMonitors)
      .catch((e: unknown) => {
        if (!controller.signal.aborted) console.error('Falha ao listar monitores:', e)
      })
    setPreviewTick((x) => x + 1)
    startPreview()
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      controller.abort()
      document.removeEventListener('visibilitychange', onVisibility)
      if (timer) clearInterval(timer)
    }
  }, [liveOpen])

  // Watch loop: cada chamada de /api/chat carrega um AbortController próprio,
  // abortado ao desligar o modo — sem isso a requisição em voo (até ~30s de
  // inferência) continua rodando no backend depois do painel fechar.
  const watchLoop = useCallback(async () => {
    while (watchActiveRef.current && liveOpenRef.current) {
      const controller = new AbortController()
      watchAbortRef.current = controller
      try {
        const res = await chat(
          'Observe esta captura das minhas telas. Descreva em no máximo 2 frases o que está sendo mostrado agora. Se for essencialmente igual à última observação, responda exatamente: sem mudanças',
          sessionIdRef.current,
          true,
          null,
          monitorSelRef.current,
          null,
          controller.signal,
        )
        const txt = res.response.trim()
        setSessionId(res.session_id)
        sessionIdRef.current = res.session_id
        if (txt && !/^sem mudanças[.!]?$/i.test(txt)) {
          setMessages((m) => [...m, { role: 'assistant', content: `👁 ${txt}` }])
        }
      } catch {
        // Abort (painel fechado) ou erro de rede — o loop só continua se
        // ainda estiver ativo; caso contrário, sai.
        if (!watchActiveRef.current || !liveOpenRef.current) break
      } finally {
        if (watchAbortRef.current === controller) watchAbortRef.current = null
      }
      const until = Date.now() + 25000
      while (Date.now() < until && watchActiveRef.current && liveOpenRef.current) {
        await new Promise((r) => setTimeout(r, 500))
      }
    }
  }, [sessionIdRef, setMessages, setSessionId])

  useEffect(() => {
    if (watchMode && liveOpen) {
      watchActiveRef.current = true
      void watchLoop()
    } else {
      watchActiveRef.current = false
      watchAbortRef.current?.abort()
    }
    return () => {
      watchActiveRef.current = false
      watchAbortRef.current?.abort()
    }
  }, [watchMode, liveOpen, watchLoop])

  // Auto-solve: varre a tela a cada DETECT_INTERVAL_MS com OCR+regex (sem
  // modelo) e, quando encontra questões NOVAS (fingerprint não vista),
  // dispara a resolução completa uma única vez e publica no chat.
  const autoSolveLoop = useCallback(async () => {
    while (autoActiveRef.current && liveOpenRef.current) {
      const controller = new AbortController()
      autoAbortRef.current = controller
      try {
        const det = await detectScreenQuestions(monitorSelRef.current, controller.signal)
        // Painel fechou/loop desligado durante o fetch → não resolve mais nada.
        if (!autoActiveRef.current || !liveOpenRef.current) break
        const novas = det.questions.filter((q) => {
          if (!q.fingerprint) return false
          if (seenQuestionsRef.current.has(q.fingerprint)) return false
          seenQuestionsRef.current.add(q.fingerprint)
          return true
        })
        if (novas.length > 0) {
          const res = await answerScreenQuestions(
            monitorSelRef.current,
            null,
            sessionIdRef.current,
            controller.signal,
          )
          if (res.session_id) {
            setSessionId(res.session_id)
            sessionIdRef.current = res.session_id
          }
          // Monitor explícito (o mesmo do preview): o cabeçalho sempre
          // sai com o número da tela que o painel está exibindo.
          const tela = `tela ${(res.monitor ?? 0) + 1}${res.monitor_name ? ` (${res.monitor_name})` : ''}`
          const cabecalho = `🧩 ${tela} · ${novas.length} questão(ões) detectada(s) — resolvida automaticamente`
          setMessages((m) => [
            ...m,
            { role: 'user', content: '🧩 Resolva as questões da tela (auto)' },
            { role: 'assistant', content: `${cabecalho}\n\n${res.answer_text}` },
          ])
        }
      } catch (e) {
        // Abort (painel fechado) → sai; senão é erro transiente (rede,
        // 429 do rate limit) e o próximo ciclo tenta de novo.
        if (!autoActiveRef.current || !liveOpenRef.current) break
        console.warn('Auto-solve: falha na varredura de questões:', e)
      } finally {
        if (autoAbortRef.current === controller) autoAbortRef.current = null
      }
      const until = Date.now() + DETECT_INTERVAL_MS
      while (Date.now() < until && autoActiveRef.current && liveOpenRef.current) {
        await new Promise((r) => setTimeout(r, 500))
      }
    }
  }, [sessionIdRef, setMessages, setSessionId])

  useEffect(() => {
    if (autoSolve && liveOpen) {
      autoActiveRef.current = true
      void autoSolveLoop()
    } else {
      autoActiveRef.current = false
      autoAbortRef.current?.abort()
      // Desligou → limpa a memória de questões vistas para a próxima
      // ativação tratar de novo o que estiver na tela.
      if (!autoSolve) seenQuestionsRef.current.clear()
    }
    return () => {
      autoActiveRef.current = false
      autoAbortRef.current?.abort()
    }
  }, [autoSolve, liveOpen, autoSolveLoop])

  const peekScreen = useCallback(async () => {
    try {
      const shot = await captureScreen(monitorSelRef.current)
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          content: `Tela capturada.\n${shot.text ? `Texto detectado:\n${shot.text.slice(0, 500)}` : '(sem texto legível)'}`,
        },
      ])
    } catch {
      // erro tratado pelo componente pai
    }
  }, [setMessages])

  const previewSrc = useCallback(
    (monitor: number) => screenPreviewUrl(monitor),
    [],
  )

  return {
    useScreenCapture, setUseScreenCapture,
    liveOpen, setLiveOpen,
    liveMinimized, setLiveMinimized,
    watchMode, setWatchMode,
    autoSolve, setAutoSolve,
    monitors, monitorSel, setMonitorSel,
    previewTick,
    peekScreen, previewSrc,
  }
}
