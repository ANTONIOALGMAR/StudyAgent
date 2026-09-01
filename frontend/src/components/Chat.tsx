import { Suspense, lazy, useEffect, useRef, useState } from 'react'
import { AGENT3D_LABELS, type Agent3DState as FaceState } from './StudyAgent3D/agentStates'
import ActionConfirm from './ActionConfirm'
import ChatMessages from './ChatMessages'
import ChatInput from './ChatInput'
import LivePanel from './LivePanel'
import Sidebar from './Sidebar'
import EvidencePanel from './EvidencePanel'
import CameraPanel from './CameraPanel'
import PanelManager from './PanelManager'
import { type UploadedDoc } from '../api'
import { useChat } from '../hooks/useChat'
import { useVoice } from '../hooks/useVoice'
import { useScreen } from '../hooks/useScreen'

const PdfViewer = lazy(() => import('./PdfViewer'))
const StudyAgentAvatar = lazy(() => import('./StudyAgent3D/StudyAgentAvatar'))

function PanelFallback() {
  return <div style={{ padding: 20, textAlign: 'center', color: '#8b93a7' }}><span className="spinner" /> carregando…</div>
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
  const [panels, setPanels] = useState({
    exOpen: false,
    fcOpen: false,
    spOpen: false,
    stOpen: false,
    profOpen: false,
    achOpen: false,
  })

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
      if (shouldAutoOrchestrateVisuals(text)) {
        screen.setUseScreenCapture(true)
        screen.setLiveOpen(true)
      }
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

  // Handle structured actions emitted by the backend (e.g., request_permission)
  useEffect(() => {
    async function onActions(ev: Event) {
      try {
        // @ts-ignore
        const detail = ev.detail || {}
        const actions = detail.actions || []
        const original = detail.original || ''
        for (const a of actions) {
          if (a.type === 'request_permission' && a.permission === 'camera') {
            // Ask user for consent via a simple confirm modal for now
            const allow = window.confirm('O agente precisa usar a câmera para procurar este objeto. Permitir agora?')
            if (!allow) continue
            try {
              const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } })
              const video = document.createElement('video') as HTMLVideoElement
              video.srcObject = stream
              await video.play().catch(() => {})
              await new Promise((r) => setTimeout(r, 300))
              const canvas = document.createElement('canvas')
              canvas.width = video.videoWidth || 640
              canvas.height = video.videoHeight || 480
              const ctx = canvas.getContext('2d')
              if (ctx) ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
              const b64 = canvas.toDataURL('image/jpeg', 0.85).split(',')[1]
              // stop tracks
              stream.getTracks().forEach((t) => t.stop())
              // re-send the original message with image attached
              void chatHook.sendText(original, { imageB64: b64 })
            } catch (err) {
              // failed to get camera
              window.alert('Não foi possível acessar a câmera. Verifique as permissões do navegador.')
            }
          }
        }
      } catch (e) {
        // ignore
      }
    }
    window.addEventListener('studyagent:actions', onActions as EventListener)
    return () => window.removeEventListener('studyagent:actions', onActions as EventListener)
  }, [chatHook])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key === 'E') { e.preventDefault(); setEvidenceOpen((v) => !v) }
      if (e.ctrlKey && e.shiftKey && e.key === 'S') { e.preventDefault(); screen.setUseScreenCapture((v) => !v) }
      if (e.ctrlKey && e.shiftKey && e.key === 'X') { e.preventDefault(); setPanels(p => ({ ...p, exOpen: !p.exOpen })) }
      if (e.ctrlKey && e.shiftKey && e.key === 'F') { e.preventDefault(); setPanels(p => ({ ...p, fcOpen: !p.fcOpen })) }
      if (e.ctrlKey && e.shiftKey && e.key === 'L') { e.preventDefault(); screen.setLiveOpen((v) => !v) }
      if (e.ctrlKey && e.shiftKey && e.key === 'H') { e.preventDefault(); setPanels(p => ({ ...p, stOpen: !p.stOpen })) }
      if (e.key === 'Escape') {
        if (evidenceOpen) setEvidenceOpen(false)
        else if (panels.exOpen) setPanels(p => ({ ...p, exOpen: false }))
        else if (panels.fcOpen) setPanels(p => ({ ...p, fcOpen: false }))
        else if (panels.spOpen) setPanels(p => ({ ...p, spOpen: false }))
        else if (panels.stOpen) setPanels(p => ({ ...p, stOpen: false }))
        else if (panels.profOpen) setPanels(p => ({ ...p, profOpen: false }))
        else if (panels.achOpen) setPanels(p => ({ ...p, achOpen: false }))
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [evidenceOpen, panels, screen])

  function shouldAutoOrchestrateVisuals(text: string) {
    const normalized = text.toLowerCase()
    const envKeywords = [
      'onde está', 'onde fica', 'localize', 'localizar', 'encontre', 'achar', 'procure',
      'o que tem', 'o que há', 'o que ha', 'quais objetos', 'quais itens',
      'me mostre o ambiente', 'observe o ambiente', 'veja o ambiente',
      'qual objeto está', 'qual coisa está', 'what is in the room', 'where is the',
    ]
    return envKeywords.some((keyword) => normalized.includes(keyword))
  }

  function shouldAutoOpenCamera(text: string) {
    const normalized = text.toLowerCase()
    return /c[aâ]mera|camera|imagem|foto|ambiente|visualizar|vejo|o que tem na imagem|o que vê|o que ve|onde está|localize|procure/.test(normalized)
  }

  function send() {
    const text = input.trim()
    setInput('')
    if (shouldAutoOrchestrateVisuals(text) || shouldAutoOpenCamera(text)) {
      screen.setUseScreenCapture(true)
      screen.setLiveOpen(true)
      setCamOpen(true)
    }
    void chatHook.sendText(text)
  }

  const camStreamRef = useRef<MediaStream | null>(null)

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
    { icon: '📷', label: 'Câmera', active: camOpen, onClick: () => setCamOpen(!camOpen), title: 'Aponte a câmera e pergunte' },
    { icon: '📎', label: 'Anexar PDF', active: !!activeDoc, onClick: () => fileInputRef.current?.click(), title: 'Estudar um documento' },
    { icon: '📖', label: 'Ler PDF', active: !!viewerDoc, onClick: () => setViewerDoc(viewerDoc ? null : activeDoc), title: 'Abrir/fechar leitor de documentos' },
    { icon: '🎯', label: 'Exercícios', active: panels.exOpen, onClick: () => setPanels(p => ({ ...p, exOpen: !p.exOpen })), title: 'Gerar exercícios com correção' },
    { icon: '🃏', label: 'Flashcards', active: panels.fcOpen, onClick: () => setPanels(p => ({ ...p, fcOpen: !p.fcOpen })), title: 'Revisão espaçada com flashcards' },
    { icon: '📋', label: 'Plano de estudo', active: panels.spOpen, onClick: () => setPanels(p => ({ ...p, spOpen: !p.spOpen })), title: 'Gerar plano de estudo estruturado' },
    { icon: '📊', label: 'Progresso', active: panels.stOpen, onClick: () => setPanels(p => ({ ...p, stOpen: !p.stOpen })), title: 'Dashboard de progresso' },
    { icon: '👤', label: 'Perfil', active: panels.profOpen, onClick: () => setPanels(p => ({ ...p, profOpen: !p.profOpen })), title: 'Perfil do aluno e análise de aprendizado' },
    { icon: '🏆', label: 'Conquistas', active: panels.achOpen, onClick: () => setPanels(p => ({ ...p, achOpen: !p.achOpen })), title: 'Conquistas e sequências de estudo' },
    { icon: '👁', label: 'Olhar agora', active: false, onClick: screen.peekScreen, title: 'Captura rápida da tela atual' },
    { icon: '🎭', label: 'Modo palco', active: stage, onClick: () => setStage(true), title: 'Rosto em tela cheia' },
  ]

  return (
    <div className="app-shell">
      <Sidebar items={sidebarItems} />
      <div className="chat">
        <div className="chat-header">
          <Suspense fallback={<div className="face-fallback" />}>
            <StudyAgentAvatar state={faceState} size={84} voice={voice.voiceOn} sensitivity={3.4} />
          </Suspense>
          <div className="face-label">
            <span className="face-title">StudyAgent</span>
            <span className="face-status">{AGENT3D_LABELS[faceState]}</span>
          </div>
          <div className="header-actions">
            <button className="btn-screen" onClick={() => setStage(true)} title="Ampliar o rosto (modo palco)">⤢</button>
          </div>
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
          <PanelManager 
            panels={panels} 
            setPanels={(id, val) => setPanels(p => ({ ...p, [`${id}Open` as keyof typeof panels]: val }))} 
            onMood={flashReaction} 
          />
        </Suspense>

        {camOpen && (
          <CameraPanel 
            isOpen={camOpen} 
            onClose={() => setCamOpen(false)} 
            loading={chatHook.loading}
            onCapture={(b64, question) => {
              setCamOpen(false)
              void chatHook.sendText(question, { imageB64: b64 })
            }}
          />
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
              <Suspense fallback={<div className="face-fallback" />}>
                <StudyAgentAvatar
                  state={faceState}
                  size={Math.min(window.innerWidth, window.innerHeight) * 0.5}
                  controls
                  voice={voice.voiceOn}
                  sensitivity={3.4}
                />
              </Suspense>
              <p className="stage-label">{AGENT3D_LABELS[faceState]}</p>
              <button className={`btn-screen ${voice.voiceOn ? 'active' : ''}`} onClick={() => voice.setVoiceOn(!voice.voiceOn)} title="Responder por voz">🔊</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
