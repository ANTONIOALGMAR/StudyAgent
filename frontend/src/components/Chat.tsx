import { Suspense, lazy, useEffect, useRef, useState } from 'react'
import AgentFace, { type FaceState } from './AgentFace'
import ActionConfirm from './ActionConfirm'
import ChatMessages from './ChatMessages'
import ChatInput from './ChatInput'
import LivePanel from './LivePanel'
import Sidebar from './Sidebar'
import EvidencePanel from './EvidencePanel'
import { type UploadedDoc } from '../api'
import { useChat } from '../hooks/useChat'
import { useVoice } from '../hooks/useVoice'
import { useScreen } from '../hooks/useScreen'

const ExercisesPanel = lazy(() => import('./ExercisesPanel'))
const FlashcardsPanel = lazy(() => import('./FlashcardsPanel'))
const PdfViewer = lazy(() => import('./PdfViewer'))
const AchievementsPanel = lazy(() => import('./AchievementsPanel'))
const ProfilePanel = lazy(() => import('./ProfilePanel'))
const StatsPanel = lazy(() => import('./StatsPanel'))
const StudyPlanPanel = lazy(() => import('./StudyPlanPanel'))

function PanelFallback() {
  return <div style={{ padding: 20, textAlign: 'center', color: '#8b93a7' }}><span className="spinner" /> carregando…</div>
}

const FACE_LABELS: Record<FaceState, string> = {
  idle: 'pronto para ajudar',
  listening: 'ouvindo você…',
  recording: 'gravando sua voz',
  thinking: 'pensando…',
  speaking: 'falando',
  error: 'ops, algo deu errado',
  happy: 'ficou feliz com você! 🎉',
  concerned: 'quer te ajudar a melhorar',
  curious: 'fez uma pergunta pra você',
}

export default function Chat() {
  const [input, setInput] = useState('')
  const [reaction, setReaction] = useState<FaceState | null>(null)
  const reactionTimerRef = useRef<number | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [activeDoc, setActiveDoc] = useState<UploadedDoc | null>(() => {
    try {
      const saved = localStorage.getItem('studyagent.doc')
      return saved ? (JSON.parse(saved) as UploadedDoc) : null
    } catch { return null }
  })
  const [viewerDoc, setViewerDoc] = useState<UploadedDoc | null>(null)
  const [evidenceOpen, setEvidenceOpen] = useState(false)
  const [stage, setStage] = useState(false)
  const [camOpen, setCamOpen] = useState(false)
  const [exOpen, setExOpen] = useState(false)
  const [fcOpen, setFcOpen] = useState(false)
  const [spOpen, setSpOpen] = useState(false)
  const [stOpen, setStOpen] = useState(false)
  const [profOpen, setProfOpen] = useState(false)
  const [achOpen, setAchOpen] = useState(false)

  useEffect(() => {
    if (activeDoc) localStorage.setItem('studyagent.doc', JSON.stringify(activeDoc))
    else localStorage.removeItem('studyagent.doc')
  }, [activeDoc])

  function flashReaction(mood: FaceState) {
    if (reactionTimerRef.current) window.clearTimeout(reactionTimerRef.current)
    setReaction(mood === 'idle' ? null : mood)
    reactionTimerRef.current = window.setTimeout(() => setReaction(null), 6000)
  }

  const chatHook = useChat({
    useScreen: false,
    liveOpen: false,
    monitorSel: 0,
    activeDoc,
    onMood: flashReaction,
  })

  const voice = useVoice({
    onUserMessage: (text) => {
      void chatHook.sendText(text, { viaVoice: true, awaitSpeech: true, onSpeech: voice.playSpeechAwait })
    },
  })

  // Fix session ID ref
  useEffect(() => {
    chatHook.sessionIdRef.current = chatHook.sessionId
  }, [chatHook.sessionId])

  const screen = useScreen({
    sessionIdRef: chatHook.sessionIdRef,
    setMessages: chatHook.setMessages,
    setSessionId: chatHook.setSessionId,
  })

  // Update chatHook with actual screen state
  useEffect(() => {
    chatHook.setUseScreen(screen.useScreenCapture)
    chatHook.setLiveOpen(screen.liveOpen)
    chatHook.setMonitorSel(screen.monitorSel)
  }, [screen.useScreenCapture, screen.liveOpen, screen.monitorSel])

  useEffect(() => {
    if (!stage) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setStage(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [stage])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key === 'E') { e.preventDefault(); setEvidenceOpen((v) => !v) }
      if (e.ctrlKey && e.shiftKey && e.key === 'S') { e.preventDefault(); screen.setUseScreenCapture((v) => !v) }
      if (e.ctrlKey && e.shiftKey && e.key === 'X') { e.preventDefault(); setExOpen((v) => !v) }
      if (e.ctrlKey && e.shiftKey && e.key === 'F') { e.preventDefault(); setFcOpen((v) => !v) }
      if (e.ctrlKey && e.shiftKey && e.key === 'L') { e.preventDefault(); screen.setLiveOpen((v) => !v) }
      if (e.ctrlKey && e.shiftKey && e.key === 'H') { e.preventDefault(); setStOpen((v) => !v) }
      if (e.key === 'Escape') {
        if (evidenceOpen) setEvidenceOpen(false)
        else if (exOpen) setExOpen(false)
        else if (fcOpen) setFcOpen(false)
        else if (spOpen) setSpOpen(false)
        else if (stOpen) setStOpen(false)
        else if (profOpen) setProfOpen(false)
        else if (achOpen) setAchOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [evidenceOpen, exOpen, fcOpen, spOpen, stOpen, profOpen, achOpen, screen])

  function send() {
    const text = input.trim()
    setInput('')
    void chatHook.sendText(text)
  }

  function snapAndAsk() {
    const video = document.querySelector<HTMLVideoElement>('.camera-panel video')
    if (!video || !video.videoWidth) return
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext('2d')?.drawImage(video, 0, 0)
    const b64 = canvas.toDataURL('image/jpeg', 0.85).split(',')[1]
    setCamOpen(false)
    const question = input.trim() || 'O que você vê nesta imagem?'
    setInput('')
    void chatHook.sendText(question, { imageB64: b64 })
  }

  const camStreamRef = useRef<MediaStream | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)

  async function openCamera() {
    chatHook.setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 } } })
      camStreamRef.current = stream
      setCamOpen(true)
    } catch {
      chatHook.setError('Câmera não autorizada no navegador')
    }
  }

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

  useEffect(() => {
    return () => {
      voice.cleanup()
      camStreamRef.current?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  const faceState: FaceState =
    chatHook.error ? 'error'
    : voice.speaking ? 'speaking'
    : voice.handsFree && voice.hfState === 'recording' ? 'recording'
    : voice.handsFree && voice.hfState === 'listening' ? 'listening'
    : chatHook.loading ? 'thinking'
    : reaction ?? 'idle'

  const statusLabel =
    voice.hfState === 'listening' ? '🎧 ouvindo… fale quando quiser'
    : voice.hfState === 'recording' ? '🔴 gravando… termine sua frase'
    : voice.hfState === 'processing' ? '🧠 pensando…'
    : voice.hfState === 'speaking' ? '🗣 falando…'
    : ''

  const sidebarItems = [
    { icon: '🖥', label: 'Anexar tela', active: screen.useScreenCapture, onClick: () => screen.setUseScreenCapture(!screen.useScreenCapture), title: 'Anexar captura de tela à mensagem' },
    { icon: '📺', label: 'Telas ao vivo', active: screen.liveOpen, onClick: () => { screen.setLiveMinimized(false); screen.setLiveOpen(!screen.liveOpen) }, title: 'Acompanhe o que o agente vê' },
    { icon: '📷', label: 'Câmera', active: camOpen, onClick: () => camOpen ? closeCamera() : void openCamera(), title: 'Aponte a câmera e pergunte' },
    { icon: '📎', label: 'Anexar PDF', active: !!activeDoc, onClick: () => fileInputRef.current?.click(), title: 'Estudar um documento' },
    { icon: '📖', label: 'Ler PDF', active: !!viewerDoc, onClick: () => setViewerDoc(viewerDoc ? null : activeDoc), title: 'Abrir/fechar leitor de documentos' },
    { icon: '🎯', label: 'Exercícios', active: exOpen, onClick: () => setExOpen(!exOpen), title: 'Gerar exercícios com correção' },
    { icon: '🃏', label: 'Flashcards', active: fcOpen, onClick: () => setFcOpen(!fcOpen), title: 'Revisão espaçada com flashcards' },
    { icon: '📋', label: 'Plano de estudo', active: spOpen, onClick: () => setSpOpen(!spOpen), title: 'Gerar plano de estudo estruturado' },
    { icon: '📊', label: 'Progresso', active: stOpen, onClick: () => setStOpen(!stOpen), title: 'Dashboard de progresso' },
    { icon: '👤', label: 'Perfil', active: profOpen, onClick: () => setProfOpen(!profOpen), title: 'Perfil do aluno e análise de aprendizado' },
    { icon: '🏆', label: 'Conquistas', active: achOpen, onClick: () => setAchOpen(!achOpen), title: 'Conquistas e sequências de estudo' },
    { icon: '👁', label: 'Olhar agora', active: false, onClick: screen.peekScreen, title: 'Captura rápida da tela atual' },
    { icon: '🎭', label: 'Modo palco', active: stage, onClick: () => setStage(true), title: 'Rosto em tela cheia' },
  ]

  return (
    <div className="app-shell">
      <Sidebar items={sidebarItems} />
      <div className="chat">
        <div className="chat-header">
          <AgentFace state={faceState} size={84} />
          <div className="face-label">
            <span className="face-title">StudyAgent</span>
            <span className="face-status">{FACE_LABELS[faceState]}</span>
          </div>
          <button className="btn-screen btn-stage" onClick={() => setStage(true)} title="Ampliar o rosto (modo palco)">⤢</button>
        </div>

        <ChatMessages messages={chatHook.messages} loading={chatHook.loading} handsFree={voice.handsFree} error={chatHook.error} />

        {activeDoc && (
          <div className="doc-chip">
            📄 {activeDoc.name}
            <button onClick={() => setViewerDoc(activeDoc)} title="Abrir leitor de PDF">👁</button>
            <button onClick={() => setActiveDoc(null)} title="Remover documento">✕</button>
          </div>
        )}

        <Suspense fallback={<PanelFallback />}>
          {viewerDoc && <PdfViewer doc={viewerDoc} onClose={() => setViewerDoc(null)} />}
        </Suspense>

        {voice.handsFree && statusLabel && <div className={`status-pill st-${voice.hfState}`}>{statusLabel}</div>}

        <ActionConfirm />

        {screen.liveOpen && !screen.liveMinimized && (
          <LivePanel
            monitors={screen.monitors}
            monitorSel={screen.monitorSel}
            setMonitorSel={screen.setMonitorSel}
            previewTick={screen.previewTick}
            watchMode={screen.watchMode}
            setWatchMode={screen.setWatchMode}
            onClose={() => { screen.setWatchMode(false); screen.setLiveOpen(false) }}
            onMinimize={() => screen.setLiveMinimized(true)}
          />
        )}

        {screen.liveOpen && screen.liveMinimized && (
          <button className="live-minimized" onClick={() => screen.setLiveMinimized(false)} title="Restaurar painel ao vivo">
            📺 ao vivo ▴
          </button>
        )}

        <Suspense fallback={<PanelFallback />}>
          {exOpen && (
            <div className="live-panel exercises-panel">
              <div className="live-head"><strong>🎯 exercícios</strong><button className="btn-screen" onClick={() => setExOpen(false)}>✕</button></div>
              <ExercisesPanel onMood={(m) => flashReaction(m as FaceState)} />
            </div>
          )}

          {fcOpen && (
            <div className="live-panel flashcards-panel">
              <div className="live-head"><strong>🃏 flashcards</strong><button className="btn-screen" onClick={() => setFcOpen(false)}>✕</button></div>
              <FlashcardsPanel onMood={(m) => flashReaction(m as FaceState)} />
            </div>
          )}

          {spOpen && (
            <div className="live-panel studyplan-panel">
              <div className="live-head"><strong>📋 plano de estudo</strong><button className="btn-screen" onClick={() => setSpOpen(false)}>✕</button></div>
              <StudyPlanPanel onMood={(m) => flashReaction(m as FaceState)} />
            </div>
          )}

          {stOpen && (
            <div className="live-panel stats-panel">
              <div className="live-head"><strong>📊 progresso</strong><button className="btn-screen" onClick={() => setStOpen(false)}>✕</button></div>
              <StatsPanel />
            </div>
          )}

          {profOpen && (
            <div className="live-panel profile-panel">
              <div className="live-head"><strong>👤 perfil</strong><button className="btn-screen" onClick={() => setProfOpen(false)}>✕</button></div>
              <ProfilePanel />
            </div>
          )}

          {achOpen && (
            <div className="live-panel achievements-panel">
              <div className="live-head"><strong>🏆 conquistas</strong><button className="btn-screen" onClick={() => setAchOpen(false)}>✕</button></div>
              <AchievementsPanel />
            </div>
          )}
        </Suspense>

        {camOpen && (
          <div className="camera-panel">
            <video ref={videoRef} autoPlay muted playsInline />
            <div className="camera-actions">
              <button className="btn-send" onClick={snapAndAsk} disabled={chatHook.loading}>📸 capturar e perguntar</button>
              <button className="btn-screen" onClick={closeCamera}>✕ fechar</button>
            </div>
          </div>
        )}

        {(chatHook.lastEvidence || chatHook.lastToolsUsed.length > 0) && (
          <button
            className="btn-screen evidence-toggle"
            onClick={() => setEvidenceOpen(!evidenceOpen)}
            title="Mostrar evidência da última resposta"
            style={{ position: 'fixed', bottom: 80, right: 16, zIndex: 999, borderRadius: 999, width: 36, height: 36, fontSize: 14, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: evidenceOpen ? '#334155' : '#1e293b', border: '1px solid #475569', color: '#94a3b8', cursor: 'pointer' }}
          >
            🔍
          </button>
        )}

        {evidenceOpen && (
          <EvidencePanel evidence={chatHook.lastEvidence} toolsUsed={chatHook.lastToolsUsed} onClose={() => setEvidenceOpen(false)} />
        )}

        <ChatInput
          input={input}
          setInput={setInput}
          onSend={send}
          onToggleRecording={voice.toggleRecording}
          recording={voice.recording}
          loading={chatHook.loading}
          handsFree={voice.handsFree}
          voiceOn={voice.voiceOn}
          setVoiceOn={voice.setVoiceOn}
          onStartHandsFree={voice.startHandsFree}
          onStopHandsFree={voice.stopHandsFree}
          onFileChosen={(file) => {
            void chatHook.loadDocument(file).then((doc) => { if (doc) { setActiveDoc(doc); setViewerDoc(doc) } })
          }}
        />

        {stage && (
          <div className="stage-overlay" onClick={() => setStage(false)}>
            <button className="btn-screen stage-close" onClick={() => setStage(false)} title="Voltar (Esc)">✕</button>
            <div className="stage-inner" onClick={(e) => e.stopPropagation()}>
              <AgentFace state={faceState} size={Math.min(window.innerWidth, window.innerHeight) * 0.62} />
              <p className="stage-label">{FACE_LABELS[faceState]}</p>
              <button className={`btn-screen ${voice.voiceOn ? 'active' : ''}`} onClick={() => voice.setVoiceOn(!voice.voiceOn)} title="Responder por voz">🔊</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
