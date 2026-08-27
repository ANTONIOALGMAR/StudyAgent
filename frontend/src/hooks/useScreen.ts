import { useCallback, useEffect, useRef, useState } from 'react'
import { captureScreen, getMonitors, screenPreviewUrl, chat, type MonitorInfo } from '../api'

export interface UseScreenOptions {
  sessionIdRef: React.MutableRefObject<string | null>
  setMessages: React.Dispatch<React.SetStateAction<{ role: 'user' | 'assistant'; content: string }[]>>
  setSessionId: (id: string) => void
}

export function useScreen({ sessionIdRef, setMessages, setSessionId }: UseScreenOptions) {
  const [useScreenCapture, setUseScreenCapture] = useState(false)
  const [liveOpen, setLiveOpen] = useState(false)
  const [liveMinimized, setLiveMinimized] = useState(false)
  const [watchMode, setWatchMode] = useState(false)
  const [monitors, setMonitors] = useState<MonitorInfo[]>([])
  const [monitorSel, setMonitorSel] = useState(0)
  const [previewTick, setPreviewTick] = useState(0)
  const watchActiveRef = useRef(false)
  const monitorSelRef = useRef(0)
  const liveOpenRef = useRef(false)

  useEffect(() => { monitorSelRef.current = monitorSel }, [monitorSel])
  useEffect(() => { liveOpenRef.current = liveOpen }, [liveOpen])

  useEffect(() => {
    if (!liveOpen) return
    void getMonitors().then(setMonitors)
    const t = setInterval(() => setPreviewTick((x) => x + 1), 2000)
    return () => clearInterval(t)
  }, [liveOpen])

  const watchLoop = useCallback(async () => {
    while (watchActiveRef.current && liveOpenRef.current) {
      try {
        const res = await chat(
          'Observe esta captura das minhas telas. Descreva em no máximo 2 frases o que está sendo mostrado agora. Se for essencialmente igual à última observação, responda exatamente: sem mudanças',
          sessionIdRef.current,
          true,
          null,
          monitorSelRef.current,
        )
        const txt = res.response.trim()
        setSessionId(res.session_id)
        sessionIdRef.current = res.session_id
        if (txt && !/^sem mudanças[.!]?$/i.test(txt)) {
          setMessages((m) => [...m, { role: 'assistant', content: `👁 ${txt}` }])
        }
      } catch {
        break
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
    }
    return () => { watchActiveRef.current = false }
  }, [watchMode, liveOpen, watchLoop])

  const peekScreen = useCallback(async () => {
    try {
      const shot = await captureScreen()
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
    monitors, monitorSel, setMonitorSel,
    previewTick,
    peekScreen, previewSrc,
  }
}
