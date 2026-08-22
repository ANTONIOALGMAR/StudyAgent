import { useEffect, useRef, useState } from 'react'
import { chat, captureScreen, transcribeAudio, speak, type ChatResponse } from '../api'

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

  useEffect(() => {
    return () => {
      hfActiveRef.current = false
      streamRef.current?.getTracks().forEach((t) => t.stop())
      void audioCtxRef.current?.close().catch(() => {})
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

  async function sendText(text: string, opts: { viaVoice?: boolean; awaitSpeech?: boolean } = {}) {
    if (!text || loading) return
    setError(null)
    setMessages((m) => [...m, { role: 'user', content: opts.viaVoice ? `🎙 ${text}` : text }])
    setLoading(true)
    try {
      const res: ChatResponse = await chat(text, sessionId, useScreen)
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

      {handsFree && statusLabel && <div className={`status-pill st-${hfState}`}>{statusLabel}</div>}

      <div className="chat-input">
        <button
          className={`btn-screen ${useScreen ? 'active' : ''}`}
          onClick={() => setUseScreen(!useScreen)}
          title="Anexar captura de tela à mensagem"
        >
          🖥
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
