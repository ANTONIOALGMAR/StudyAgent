import { useEffect, useRef, useState } from 'react'
import { documentAudioUrl, documentFileUrl, getDocAudioPlan, type UploadedDoc } from '../api'

interface Props {
  doc: UploadedDoc
  onClose: () => void
}

export default function PdfViewer({ doc, onClose }: Props) {
  const [audioOn, setAudioOn] = useState(false)
  const [total, setTotal] = useState(0)
  const [kind, setKind] = useState<'página' | 'parte'>('página')
  const [idx, setIdx] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [loading, setLoading] = useState(false)
  const playerRef = useRef<HTMLAudioElement | null>(null)

  useEffect(
    () => () => {
      playerRef.current?.pause()
    },
    [],
  )

  async function tocar(parte: number) {
    setLoading(true)
    playerRef.current?.pause()
    const player = new Audio(documentAudioUrl(doc.id, parte))
    playerRef.current = player
    setIdx(parte)
    player.onended = () => {
      if (parte + 1 < total) void tocar(parte + 1)
      else setPlaying(false)
    }
    player.onerror = () => setPlaying(false)
    try {
      await player.play()
      setPlaying(true)
    } catch {
      setPlaying(false)
    } finally {
      setLoading(false)
    }
  }

  async function iniciarAudiobook() {
    if (audioOn) {
      playerRef.current?.pause()
      setAudioOn(false)
      setPlaying(false)
      return
    }
    try {
      const plano = await getDocAudioPlan(doc.id)
      setTotal(plano.total)
      setKind(plano.kind)
      setAudioOn(true)
      await tocar(0)
    } catch {
      setAudioOn(false)
    }
  }

  function alternar() {
    const player = playerRef.current
    if (!player) return
    if (playing) {
      player.pause()
      setPlaying(false)
    } else {
      void player.play().then(() => setPlaying(true)).catch(() => {})
    }
  }

  return (
    <div className="live-panel pdf-panel">
      <div className="live-head">
        <strong>📄 {doc.name}</strong>
        <span className="pdf-pages">
          {doc.pages} página{doc.pages > 1 ? 's' : ''}
        </span>
        <button
          className={`btn-screen${audioOn ? ' active' : ''}`}
          onClick={() => void iniciarAudiobook()}
          title={audioOn ? 'Parar audiobook' : 'Ouvir documento em áudio'}
        >
          🎧
        </button>
        <a
          className="btn-screen"
          href={documentFileUrl(doc.id)}
          target="_blank"
          rel="noreferrer"
          title="Abrir em nova aba"
        >
          ↗
        </a>
        <button className="btn-screen" onClick={onClose} title="Fechar leitor">
          ✕
        </button>
      </div>
      {audioOn && (
        <div className="audio-bar">
          <button
            className="btn-screen"
            disabled={idx === 0 || loading}
            onClick={() => void tocar(idx - 1)}
            title={`${kind} anterior`}
          >
            ◀
          </button>
          <button
            className="btn-screen"
            onClick={alternar}
            disabled={loading}
            title={playing ? 'Pausar' : 'Continuar'}
          >
            {playing ? '⏸' : '▶'}
          </button>
          <button
            className="btn-screen"
            disabled={idx + 1 >= total || loading}
            onClick={() => void tocar(idx + 1)}
            title={`Próxima ${kind}`}
          >
            ▶▶
          </button>
          <button
            className="btn-screen"
            onClick={() => {
              playerRef.current?.pause()
              setAudioOn(false)
              setPlaying(false)
            }}
            title="Parar"
          >
            ⏹
          </button>
          <span className="audio-label">
            {loading ? 'gerando áudio…' : `${kind} ${idx + 1} de ${total}`}
          </span>
        </div>
      )}
      <iframe
        src={`${documentFileUrl(doc.id)}#toolbar=1&view=FitH`}
        title={`Visualização de ${doc.name}`}
        className="pdf-frame"
      />
    </div>
  )
}
