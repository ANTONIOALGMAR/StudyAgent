import { useRef, useEffect, useState } from 'react'
import { getProfile, recognizeFace, registerFace, saveProfile } from '../api'

interface CameraPanelProps {
  isOpen: boolean
  onClose: () => void
  onCapture: (b64: string, question: string) => void
  loading: boolean
}

export default function CameraPanel({ isOpen, onClose, onCapture, loading }: CameraPanelProps) {
  const camStreamRef = useRef<MediaStream | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const [faceMsg, setFaceMsg] = useState<string | null>(null)
  const [faceBusy, setFaceBusy] = useState(false)
  const [input, setInput] = useState('')

  useEffect(() => {
    if (isOpen) {
      openCamera()
    } else {
      closeCamera()
    }
    return () => closeCamera()
  }, [isOpen])

  async function openCamera() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        video: { width: { ideal: 1280 }, height: { ideal: 720 } } 
      })
      camStreamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        void videoRef.current.play().catch(() => {})
      }
    } catch {
      alert('Câmera não autorizada no navegador')
    }
  }

  function closeCamera() {
    camStreamRef.current?.getTracks().forEach((t) => t.stop())
    camStreamRef.current = null
  }

  function captureFrame(): string | null {
    const video = videoRef.current
    if (!video || !video.videoWidth) return null
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const ctx = canvas.getContext('2d')
    if (!ctx) return null
    ctx.drawImage(video, 0, 0)
    return canvas.toDataURL('image/jpeg', 0.85).split(',')[1]
  }

  function handleSnap() {
    const b64 = captureFrame()
    if (!b64) return
    const question = input.trim() || 'O que você vê nesta imagem?'
    setInput('')
    onCapture(b64, question)
  }

  async function syncFaceProfile(name: string) {
    try {
      const current = await getProfile().catch(() => null)
      await saveProfile(
        name,
        current?.grade ?? '',
        current?.school ?? '',
        current?.preferences ?? '',
      )
    } catch {
      // Silencia falha de sincronização para não bloquear reconhecimento.
    }
  }

  async function handleRecognize() {
    const b64 = captureFrame()
    if (!b64) { setFaceMsg('Aguarde a câmera estabilizar…'); return }
    setFaceBusy(true)
    setFaceMsg(null)
    try {
      const res = await recognizeFace(b64)
      if (res.name) {
        void syncFaceProfile(res.name)
        setFaceMsg(`Olá, ${res.name}! Bem-vindo(a) de volta 👋`)
      } else if (!res.present) {
        setFaceMsg('Nenhum rosto claro detectado na imagem.')
      } else {
        setFaceMsg('Rosto detectado, mas não cadastrado. Use "Cadastrar rosto".')
      }
    } catch (e) {
      setFaceMsg(e instanceof Error ? e.message : 'Falha no reconhecimento facial')
    } finally {
      setFaceBusy(false)
    }
  }

  async function handleRegisterFace() {
    const b64 = captureFrame()
    if (!b64) { setFaceMsg('Aguarde a câmera estabilizar…'); return }
    const name = window.prompt('Como devo chamar você? (seu nome)')
    if (!name || !name.trim()) return
    const cleanName = name.trim()
    setFaceBusy(true)
    setFaceMsg(null)
    try {
      const res = await registerFace(cleanName, b64)
      void syncFaceProfile(res.name)
      setFaceMsg(`Rosto cadastrado como "${res.name}". Agora posso reconhecê-lo(a)!`)
    } catch (e) {
      setFaceMsg(e instanceof Error ? e.message : 'Falha ao cadastrar rosto')
    } finally {
      setFaceBusy(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="camera-panel">
      <video ref={videoRef} autoPlay muted playsInline />
      <div className="camera-actions">
        <input 
          className="camera-input" 
          placeholder="Pergunta opcional..." 
          value={input} 
          onChange={(e) => setInput(e.target.value)} 
        />
        <button className="btn-send" onClick={handleSnap} disabled={loading}>📸 capturar e perguntar</button>
        <button className="btn-screen" onClick={handleRecognize} disabled={faceBusy}>👤 reconhecer</button>
        <button className="btn-screen" onClick={handleRegisterFace} disabled={faceBusy}>✍ cadastrar rosto</button>
        <button className="btn-screen" onClick={onClose}>✕ fechar</button>
      </div>
      {faceMsg && <div className="camera-face-msg">{faceBusy ? '⏳ processando…' : faceMsg}</div>}
    </div>
  )
}
