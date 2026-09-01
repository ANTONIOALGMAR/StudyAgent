import { useEffect, useRef, useState } from 'react'
import { getProfile, recognizeFace, saveProfile, setPermission, speak } from './api'
import Chat from './components/Chat'
import PermissionsPanel from './components/PermissionsPanel'
import Notifications from './components/Notifications'

type FaceAuthState = 'checking' | 'ready' | 'blocked' | 'authenticated'

export default function App() {
  const [permOpen, setPermOpen] = useState(true)
  const [authState, setAuthState] = useState<FaceAuthState>('checking')
  const [authError, setAuthError] = useState('')
  const [userName, setUserName] = useState('')
  const [welcomePlayed, setWelcomePlayed] = useState(false)
  const streamRef = useRef<MediaStream | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)

  const runFaceLogin = async () => {
    try {
      setAuthState('checking')
      setAuthError('')

      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
      })

      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play().catch(() => {})
      }

      await new Promise((resolve) => window.setTimeout(resolve, 500))
      const video = videoRef.current
      if (!video || !video.videoWidth || !video.videoHeight) {
        setAuthState('blocked')
        setAuthError('Não foi possível capturar a imagem da câmera. Permita o uso da câmera para continuar.')
        return
      }

      const canvas = document.createElement('canvas')
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
      const ctx = canvas.getContext('2d')
      if (!ctx) {
        setAuthState('blocked')
        setAuthError('Não foi possível processar a imagem da câmera. Tente novamente.')
        return
      }

      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
      const imageB64 = canvas.toDataURL('image/jpeg', 0.85).split(',')[1]

      const result = await recognizeFace(imageB64)
      if (!result.name) {
        setAuthState('blocked')
        setAuthError('Rosto não identificado. Posicione o rosto na câmera e tente novamente.')
        return
      }

      const current = await getProfile().catch(() => null)
      await saveProfile(
        result.name,
        current?.grade ?? '',
        current?.school ?? '',
        current?.preferences ?? '',
      )
      await Promise.all([
        setPermission('camera', true),
        setPermission('screen_capture', true),
      ])
      setUserName(result.name)
      setAuthState('ready')
      setAuthError('')
    } catch {
      setAuthState('blocked')
      setAuthError('Câmera não autorizada ou indisponível. Permita o acesso da câmera para entrar no StudyAgent.')
    } finally {
      streamRef.current?.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }
  }

  useEffect(() => {
    void runFaceLogin()
  }, [])

  useEffect(() => {
    if (authState !== 'ready' || !userName || welcomePlayed) return

    const greeting = `Olá, ${userName}! Eu sou o StudyAgent. Posso ajudar você a estudar e localizar objetos no ambiente.`
    void speak(greeting)
      .then((blob) => {
        const audio = new Audio(URL.createObjectURL(blob))
        audio.volume = 1
        void audio.play().catch(() => {})
      })
      .catch(() => {})
      .finally(() => {
        setWelcomePlayed(true)
      })

    const timer = window.setTimeout(() => {
      setAuthState('authenticated')
    }, 1800)
    return () => window.clearTimeout(timer)
  }, [authState, userName, welcomePlayed])

  return (
    <div className="app">
      <aside className={`sidebar ${permOpen ? 'perms-open' : 'perms-collapsed'}`}>
        <button
          className="ps-toggle"
          onClick={() => setPermOpen(!permOpen)}
          title={permOpen ? 'Ocultar painel' : 'Abrir painel'}
        >
          {permOpen ? '⟨' : '🎓'}
        </button>
        {permOpen && (
          <>
            <div className="logo">
              🎓 StudyAgent
              <span className="subtitle">tutor local · privado</span>
            </div>
            <PermissionsPanel />
          </>
        )}
      </aside>
      <main className="main">
        <Chat />
      </main>

      <Notifications />

      {authState !== 'authenticated' && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.78)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            backdropFilter: 'blur(6px)',
          }}
        >
          <div
            style={{
              width: 'min(480px, calc(100vw - 32px))',
              background: '#111827',
              border: '1px solid rgba(148, 163, 184, 0.2)',
              borderRadius: 18,
              padding: 24,
              textAlign: 'center',
              boxShadow: '0 20px 60px rgba(0,0,0,0.4)',
            }}
          >
            <video
              ref={videoRef}
              autoPlay
              muted
              playsInline
              style={{
                width: '100%',
                maxHeight: 220,
                borderRadius: 12,
                display: authState === 'checking' ? 'block' : 'none',
                objectFit: 'cover',
                background: '#020617',
              }}
            />

            {authState === 'checking' && (
              <>
                <div style={{ fontSize: 28, marginTop: 18 }}>👁️ verificando rosto...</div>
                <p style={{ color: '#cbd5e1', marginTop: 10 }}>Identificando o aluno para entrar no ambiente.</p>
              </>
            )}

            {authState === 'blocked' && (
              <>
                <div style={{ fontSize: 28, marginTop: 18 }}>⛔ acesso bloqueado</div>
                <p style={{ color: '#fca5a5', marginTop: 10 }}>{authError || 'Para continuar, é necessário identificar o usuário pela câmera.'}</p>
                <button
                  className="btn-screen"
                  onClick={() => void runFaceLogin()}
                  style={{ marginTop: 16 }}
                >
                  tentar novamente
                </button>
              </>
            )}

            {authState === 'ready' && (
              <>
                <div style={{ fontSize: 28, marginTop: 18 }}>✅ Olá, {userName}!</div>
                <p style={{ color: '#cbd5e1', marginTop: 10 }}>Reconhecimento facial confirmado. Você pode entrar no tutor.</p>
                <button
                  className="btn-screen"
                  onClick={() => setAuthState('authenticated')}
                  style={{ marginTop: 16 }}
                >
                  entrar
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
