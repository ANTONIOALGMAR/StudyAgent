import { useCallback, useRef, useState } from 'react'
import { transcribeAudio, speak } from '../api'
import { registerVoiceAnalyser } from '../lib/audioReactive'

export type HandsFreeState = 'off' | 'listening' | 'recording' | 'processing' | 'speaking'

const SILENCE_MS = 1500
const MIN_UTTERANCE_MS = 600
const START_THRESHOLD = 0.035
const RESUME_THRESHOLD = 0.02
const SPEAK_CAP_MS = 45000
const POLL_MS = 100

function stripForSpeech(text: string): string {
  return text.replace(/\[[^\]]*\]/g, '').replace(/[*#`_]/g, '').slice(0, 3000)
}

function rmsOf(buf: Float32Array): number {
  let sum = 0
  for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i]
  return Math.sqrt(sum / buf.length)
}

export interface UseVoiceOptions {
  onUserMessage: (text: string) => void
  onAssistantMessage?: (text: string) => void
  enabled?: boolean
}

export function useVoice({ onUserMessage }: UseVoiceOptions) {
  const [handsFree, setHandsFree] = useState(false)
  const [hfState, setHfState] = useState<HandsFreeState>('off')
  const [recording, setRecording] = useState(false)
  const [voiceOn, setVoiceOn] = useState(true)
  const [speaking, setSpeaking] = useState(false)

  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const playerRef = useRef<HTMLAudioElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const hfActiveRef = useRef(false)
  const speechSourceRef = useRef<MediaElementAudioSourceNode | null>(null)
  const speechCtxRef = useRef<AudioContext | null>(null)

  const teardownSpeechGraph = useCallback(() => {
    registerVoiceAnalyser(null)
    speechSourceRef.current?.disconnect()
    speechSourceRef.current = null
    void speechCtxRef.current?.close().catch(() => {})
    speechCtxRef.current = null
  }, [])

  const playSpeechAwait = useCallback(
    async (text: string): Promise<void> => {
      if (!voiceOn || !text.trim()) return
      try {
        // Se o texto for muito longo, podemos tentar usar o endpoint de stream
        // Mas para manter a compatibilidade imediata, usamos o speak normal.
        // A integração real do stream acontece no loop do agente.
        const blob = await speak(stripForSpeech(text))
        playerRef.current?.pause()
        const player = new Audio(URL.createObjectURL(blob))
        playerRef.current = player

        // Wire the playing speech into an analyser for real-time mouth sync
        teardownSpeechGraph()
        try {
          const ctx = new AudioContext()
          const source = ctx.createMediaElementSource(player)
          const talkAnalyser = ctx.createAnalyser()
          source.connect(talkAnalyser)
          talkAnalyser.connect(ctx.destination)
          registerVoiceAnalyser(talkAnalyser)
          speechCtxRef.current = ctx
          speechSourceRef.current = source
        } catch (e) {
          console.error('Não foi possível analisar o áudio da fala:', e)
        }

        setHfState('speaking')
        setSpeaking(true)
        try {
          await new Promise<void>((resolve) => {
            const cap = setTimeout(resolve, SPEAK_CAP_MS)
            player.onended = () => { clearTimeout(cap); resolve() }
            player.onerror = () => { clearTimeout(cap); resolve() }
            void player.play()
          })
        } finally {
          setSpeaking(false)
          teardownSpeechGraph()
        }
      } catch (e) {
        console.error('Erro ao reproduzir voz:', e)
      }
    },
    [voiceOn],
  )

  const recordUtterance = useCallback((): Promise<Blob | null> => {
    return new Promise((resolve) => {
      const analyser = analyserRef.current
      const stream = streamRef.current
      if (!analyser || !stream) { resolve(null); return }
      setHfState('listening')
      const buf = new Float32Array(analyser.fftSize)
      const blobChunks: Blob[] = []
      let isRecording = false
      let lastLoud = performance.now()
      let startedAt = 0

      const recorder = new MediaRecorder(stream)
      recorderRef.current = recorder
      recorder.ondataavailable = (e) => blobChunks.push(e.data)
      recorder.onstop = () => resolve(new Blob(blobChunks, { type: 'audio/webm' }))

      const finish = () => {
        clearInterval(timer)
        if (recorder.state === 'recording') recorder.stop()
        else resolve(null)
      }

      const timer = setInterval(() => {
        if (!hfActiveRef.current) { finish(); return }
        analyser.getFloatTimeDomainData(buf)
        const level = rmsOf(buf)
        const now = performance.now()

        if (!isRecording) {
          if (level > START_THRESHOLD) {
            isRecording = true
            startedAt = now
            lastLoud = now
            recorder.start()
            setHfState('recording')
          }
        } else {
          if (level > RESUME_THRESHOLD) lastLoud = now
          else if (now - lastLoud > SILENCE_MS && now - startedAt > MIN_UTTERANCE_MS) {
            finish()
          }
        }
      }, POLL_MS)
    })
  }, [])

  const handsFreeLoop = useCallback(async () => {
    while (hfActiveRef.current) {
      const blob = await recordUtterance()
      if (!hfActiveRef.current) break
      if (!blob || blob.size < 1000) continue
      setHfState('processing')
      try {
        const text = await transcribeAudio(blob)
        if (text) {
          onUserMessage(text)
        }
      } catch (e) {
        console.error('Erro na transcrição (hands-free):', e)
        break
      }
    }
  }, [recordUtterance, onUserMessage])

  const startHandsFree = useCallback(async () => {
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
    } catch (e) {
      console.error('Erro ao iniciar viva-voz:', e)
    }
  }, [handsFreeLoop])

  const stopHandsFree = useCallback(() => {
    hfActiveRef.current = false
    setHandsFree(false)
    setHfState('off')
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
    streamRef.current?.getTracks().forEach((t) => t.stop())
    void audioCtxRef.current?.close().catch(() => {})
    streamRef.current = null
    audioCtxRef.current = null
    analyserRef.current = null
  }, [])

  const toggleRecording = useCallback(async () => {
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
        try {
          const text = await transcribeAudio(blob)
          if (text) onUserMessage(text)
        } catch (e) {
          console.error('Erro na transcrição:', e)
        }
      }
      recorder.start()
      setRecording(true)
    } catch (e) {
      console.error('Erro ao iniciar gravação:', e)
    }
  }, [recording, onUserMessage])

  const cleanup = useCallback(() => {
    hfActiveRef.current = false
    streamRef.current?.getTracks().forEach((t) => t.stop())
    void audioCtxRef.current?.close().catch(() => {})
    streamRef.current = null
    audioCtxRef.current = null
    analyserRef.current = null
    teardownSpeechGraph()
  }, [teardownSpeechGraph])

  return {
    handsFree, setHandsFree,
    hfState, setHfState,
    recording, setRecording,
    voiceOn, setVoiceOn,
    speaking, setSpeaking,
    startHandsFree, stopHandsFree,
    toggleRecording, playSpeechAwait,
    cleanup,
    hfActiveRef,
  }
}
