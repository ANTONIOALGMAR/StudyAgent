import { useEffect, useRef, useState } from 'react'
import {
  chat,
  captureScreen,
  transcribeAudio,
  speak,
  getMonitors,
  screenPreviewUrl,
  type ChatResponse,
  type MonitorInfo,
  uploadDocument,
  type UploadedDoc,
} from '../api'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

type HandsFreeState = 'off' | 'listening' | 'recording' | 'processing' | 'speaking'

const SILENCE_MS = 1500
const MIN_UTTERANCE_MS = 600
const START_THRESHOLD = 0.035
const RESUME_THRESHOLD = 0.02
const SPEAK_CAP_MS = 45000
const POLL_MS = 100

function stripForSpeech(text: string): string {
  return text.replace(/\[[^\]]*\]/g, '').replace(/[*#`_]/g, '').slice(0, 600)
}

function rmsOf(buf: Float32Array): number {
  let sum = 0
  for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i]
  return Math.sqrt(sum / buf.length)
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [useScreen, setUseScreen] = useState(false)
  const [voiceOn, setVoiceOn] = useState(true)
  const [handsFree, setHandsFree] = useState(false)
  const [hfState, setHfState] = useState<HandsFreeState>('off')
  const [recording, setRecording] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const playerRef = useRef<HTMLAudioElement | null>(null)

  const streamRef = useRef<MediaStream | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const hfActiveRef = useRef(false)

  const camStreamRef = useRef<MediaStream | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const [camOpen, setCamOpen] = useState(false)

  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [activeDoc, setActiveDoc] = useState<UploadedDoc | null>(null)

  const [liveOpen, setLiveOpen] = useState(false)
  const [watchMode, setWatchMode] = useState(false)
  const [monitors, setMonitors] = useState<MonitorInfo[]>([])
  const [monitorSel, setMonitorSel] = useState(0)
  const [previewTick, setPreviewTick] = useState(0)
  const watchActiveRef = useRef(false)
  const sessionIdRef = useRef<string | null>(null)
  const monitorSelRef = useRef(0)
  const liveOpenRef = useRef(false)

  useEffect(() => {
    sessionIdRef.current = sessionId
  }, [sessionId])
  useEffect(() => {
    monitorSelRef.current = monitorSel
  }, [monitorSel])
  useEffect(() => {
    liveOpenRef.current = liveOpen
  }, [liveOpen])

  function closeCamera() {
    camStreamRef.current?.getTracks().forEach((t) => t.stop())
    camStreamRef.current = null
    setCamOpen(false)
  }

  useEffect(() => {
    if (camOpen && videoRef.current && camStreamRef.current) {
      videoRef.current.srcObject = camStreamRef.current
      void videoRef.current.play().catch(() => {})
    }
  }, [camOpen])

  async function openCamera() {
    setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 } },
      })
      camStreamRef.current = stream
      setCamOpen(true)
    } catch {
      setError('Câmera não autorizada no navegador (verde ao lado da barra de endereço)')
    }
  }

  useEffect(() => {
    if (!liveOpen) return
    void getMonitors().then(setMonitors)
    const t = setInterval(() => setPreviewTick((x) => x + 1), 2000)
    return () => clearInterval(t)
  }, [liveOpen])

  async function watchLoop() {
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
  }

  useEffect(() => {
    if (watchMode && liveOpen) {
      watchActiveRef.current = true
      void watchLoop()
    } else {
      watchActiveRef.current = false
    }
    return () => {
      watchActiveRef.current = false
    }
  }, [watchMode, liveOpen])

  function pickFile() {
    fileInputRef.current?.click()
  }

  async function onFileChosen(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setError(null)
    setLoading(true)
    try {
      const doc = await uploadDocument(file)
      setActiveDoc(doc)
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          content: `📄 ${doc.name} carregado (${doc.pages} página${doc.pages > 1 ? 's' : ''}). Pergunte sobre o conteúdo!`,
        },
      ])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao carregar documento')
    } finally {
      setLoading(false)
    }
  }

  function snapAndAsk() {
    const video = videoRef.current
    if (!video || !video.videoWidth) {
      setError('Câmera ainda não está pronta')
      return
    }
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext('2d')?.drawImage(video, 0, 0)
    const b64 = canvas.toDataURL('image/jpeg', 0.85).split(',')[1]
    closeCamera()
    const question =
      input.trim() || 'O que você vê nesta imagem? Identifique objetos, textos e explique.'
    setInput('')
    void sendText(question, { imageB64: b64 })
  }

  useEffect(() => {
    return () => {
      hfActiveRef.current = false
      streamRef.current?.getTracks().forEach((t) => t.stop())
      void audioCtxRef.current?.close().catch(() => {})
      camStreamRef.current?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  async function playSpeechAwait(text: string): Promise<void> {
    if (!voiceOn || !text.trim()) return
    try {
      const blob = await speak(stripForSpeech(text))
      playerRef.current?.pause()
      const player = new Audio(URL.createObjectURL(blob))
      playerRef.current = player
      setHfState('speaking')
      await new Promise<void>((resolve) => {
        const cap = setTimeout(resolve, SPEAK_CAP_MS)
        player.onended = () => {
          clearTimeout(cap)
          resolve()
        }
        player.onerror = () => {
          clearTimeout(cap)
          resolve()
        }
        void player.play()
      })
    } catch {
      // voz é opcional
    }
  }

  async function sendText(
    text: string,
    opts: { viaVoice?: boolean; awaitSpeech?: boolean; imageB64?: string } = {},
  ) {
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
        sessionId,
        useScreen || liveOpen,
        opts.imageB64 ?? null,
        monitorSelRef.current,
        activeDoc?.id ?? null,
      )
      setSessionId(res.session_id)
      const tools = res.tools_used.length > 0 ? ` [${res.tools_used.join(', ')}]` : ''
      setMessages((m) => [...m, { role: 'assistant', content: res.response + tools }])
      if (opts.awaitSpeech) await playSpeechAwait(res.response)
      else void playSpeechAwait(res.response)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro desconhecido')
    } finally {
      setLoading(false)
    }
  }

  function recordUtterance(): Promise<Blob | null> {
    return new Promise((resolve) => {
      const analyser = analyserRef.current
      const stream = streamRef.current
      if (!analyser || !stream) {
        resolve(null)
        return
      }
      setHfState('listening')
      const buf = new Float32Array(analyser.fftSize)
      const chunks: Blob[] = []
      let recording = false
      let lastLoud = performance.now()
      let startedAt = 0

      const recorder = new MediaRecorder(stream)
      recorderRef.current = recorder
      recorder.ondataavailable = (e) => chunks.push(e.data)
      recorder.onstop = () => resolve(new Blob(chunks, { type: 'audio/webm' }))

      const finish = () => {
        clearInterval(timer)
        if (recorder.state === 'recording') recorder.stop()
        else resolve(null)
      }

      const timer = setInterval(() => {
        if (!hfActiveRef.current) {
          finish()
          return
        }
        analyser.getFloatTimeDomainData(buf)
        const level = rmsOf(buf)
        const now = performance.now()

        if (!recording) {
          if (level > START_THRESHOLD) {
            recording = true
            startedAt = now
            lastLoud = now
            recorder.start()
            setHfState('recording')
          }
        } else {
          if (level > RESUME_THRESHOLD) lastLoud = now
          else if (
            now - lastLoud > SILENCE_MS &&
            now - startedAt > MIN_UTTERANCE_MS
          ) {
            finish()
          }
        }
      }, POLL_MS)
    })
  }

  async function handsFreeLoop() {
    while (hfActiveRef.current) {
      const blob = await recordUtterance()
      if (!hfActiveRef.current) break
      if (!blob || blob.size < 1000) continue
      setHfState('processing')
      setLoading(true)
      try {
        const text = await transcribeAudio(blob)
        if (!text) {
          setError('Não entendi o áudio. Fale mais perto do microfone.')
          continue
        }
        await sendText(text, { viaVoice: true, awaitSpeech: true })
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Erro na conversa automática')
        break
      } finally {
        setLoading(false)
      }
    }
  }

  async function startHandsFree() {
    setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const ctx = new AudioContext()
      const source = ctx.createMediaStreamSource(stream)
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 1024
      source.connect(analyser)
      streamRef.current = stream
      audioCtxRef.current = ctx
      analyserRef.current = analyser
      hfActiveRef.current = true
      setHandsFree(true)
      void handsFreeLoop()
    } catch {
      setError('Microfone não autorizado no navegador')
    }
  }

  function stopHandsFree() {
    hfActiveRef.current = false
    setHandsFree(false)
    setHfState('off')
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
    streamRef.current?.getTracks().forEach((t) => t.stop())
    void audioCtxRef.current?.close().catch(() => {})
    streamRef.current = null
    audioCtxRef.current = null
    analyserRef.current = null
  }

  function send() {
    const text = input.trim()
    setInput('')
    void sendText(text)
  }

  async function toggleRecording() {
    if (recording) {
      recorderRef.current?.stop()
      setRecording(false)
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      chunksRef.current = []
      const recorder = new MediaRecorder(stream)
      recorderRef.current = recorder
      recorder.ondataavailable = (e) => chunksRef.current.push(e.data)
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        if (blob.size < 1000) return
        setLoading(true)
        try {
          const text = await transcribeAudio(blob)
          if (text) await sendText(text, { viaVoice: true })
          else setError('Não entendi o áudio. Tente de novo.')
        } catch (e) {
          setError(e instanceof Error ? e.message : 'Erro na transcrição')
        } finally {
          setLoading(false)
        }
      }
      recorder.start()
      setRecording(true)
    } catch {
      setError('Microfone não autorizado no navegador')
    }
  }

  async function peekScreen() {
    try {
      const shot = await captureScreen()
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          content: `Tela capturada.\n${shot.text ? `Texto detectado:\n${shot.text.slice(0, 500)}` : '(sem texto legível)'}`,
        },
      ])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao capturar tela')
    }
  }

  const statusLabel =
    hfState === 'listening' ? '🎧 ouvindo… fale quando quiser'
    : hfState === 'recording' ? '🔴 gravando… termine sua frase'
    : hfState === 'processing' ? '🧠 pensando…'
    : hfState === 'speaking' ? '🗣 falando…'
    : ''

  return (
    <div className="chat">
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

      {activeDoc && (
        <div className="doc-chip">
          📄 {activeDoc.name}
          <button onClick={() => setActiveDoc(null)} title="Remover documento">✕</button>
        </div>
      )}

      {handsFree && statusLabel && <div className={`status-pill st-${hfState}`}>{statusLabel}</div>}

      {liveOpen && (
        <div className="live-panel">
          <div className="live-head">
            <span className="live-dot" />
            <strong>ao vivo</strong>
            <select
              value={monitorSel}
              onChange={(e) => setMonitorSel(Number(e.target.value))}
            >
              {monitors.length === 0 && <option value={0}>Todas as telas</option>}
              {monitors.map((m) =>
                m.index === 0 ? (
                  <option key={m.index} value={m.index}>
                    Todas as telas
                  </option>
                ) : (
                  <option key={m.index} value={m.index}>
                    Tela {m.index} · {m.width}×{m.height}
                  </option>
                ),
              )}
            </select>
            <button className="btn-screen" onClick={() => { setWatchMode(false); setLiveOpen(false) }}>
              ✕
            </button>
          </div>
          <img
            key={previewTick}
            src={screenPreviewUrl(monitorSel)}
            alt="tela ao vivo"
            className="live-img"
          />
          <label className="watch-toggle">
            <input
              type="checkbox"
              checked={watchMode}
              onChange={(e) => setWatchMode(e.target.checked)}
            />
            agente comenta mudanças automaticamente
          </label>
        </div>
      )}

      {camOpen && (
        <div className="camera-panel">
          <video ref={videoRef} autoPlay muted playsInline />
          <div className="camera-actions">
            <button className="btn-send" onClick={snapAndAsk} disabled={loading}>
              📸 capturar e perguntar
            </button>
            <button className="btn-screen" onClick={closeCamera}>
              ✕ fechar
            </button>
          </div>
        </div>
      )}

      <div className="chat-input">
        <button
          className={`btn-screen ${useScreen ? 'active' : ''}`}
          onClick={() => setUseScreen(!useScreen)}
          title="Anexar captura de tela à mensagem"
        >
          🖥
        </button>
        <button
          className={`btn-screen ${camOpen ? 'active' : ''}`}
          onClick={() => (camOpen ? closeCamera() : void openCamera())}
          title="Câmera: aponte, capture e pergunte"
        >
          📷
        </button>
        <button className="btn-screen" onClick={pickFile} title="Anexar PDF ou texto para estudar">
          📎
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt,.md"
          style={{ display: 'none' }}
          onChange={(e) => void onFileChosen(e)}
        />
        <button
          className={`btn-screen ${liveOpen ? 'active' : ''}`}
          onClick={() => setLiveOpen(!liveOpen)}
          title="Telas ao vivo: escolha o monitor e acompanhe o que o agente vê"
        >
          📺
        </button>
        <button className="btn-screen" onClick={peekScreen} title="Só olhar a tela agora">
          👁
        </button>
        <button
          className={`btn-mic ${recording ? 'recording' : ''}`}
          onClick={toggleRecording}
          disabled={loading || handsFree}
          title={recording ? 'Parar gravação e enviar' : 'Falar com o agente (aperte para falar)'}
        >
          🎙
        </button>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
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
          onClick={() => (handsFree ? stopHandsFree() : void startHandsFree())}
          title={handsFree ? 'Desligar modo conversa' : 'Modo conversa automática'}
        >
          {handsFree ? '⏹' : '🔄'}
        </button>
      </div>
    </div>
  )
}
