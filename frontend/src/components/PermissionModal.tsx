import { useState } from 'react'

interface Props {
  open: boolean
  permission: string
  reason?: string
  onAllow: (remember: boolean) => Promise<void>
  onDeny: () => void
}

export default function PermissionModal({ open, permission, reason, onAllow, onDeny }: Props) {
  const [remember, setRemember] = useState(false)
  const [loading, setLoading] = useState(false)

  if (!open) return null
  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 2000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ position: 'absolute', inset: 0, background: 'rgba(2,6,23,0.6)', backdropFilter: 'blur(4px)' }} />
      <div style={{ position: 'relative', width: 'min(560px, calc(100vw - 32px))', background: '#0b1220', borderRadius: 12, padding: 20, boxShadow: '0 30px 80px rgba(2,6,23,0.6)', color: '#e6eef8' }}>
        <h3 style={{ margin: 0, fontSize: 20 }}>Permissão para usar a {permission === 'camera' ? 'câmera' : permission}</h3>
        <p style={{ color: '#94a3b8', marginTop: 12 }}>{reason || 'O agente precisa acessar o hardware de visão para buscar o objeto solicitado.'}</p>

        <div style={{ marginTop: 12, padding: 12, borderRadius: 8, background: '#071028', color: '#cbd5e1' }}>
          <strong>Privacidade</strong>
          <p style={{ marginTop: 8, color: '#9ca3af' }}>
            A captura será usada apenas para responder à sua pergunta atual. Observações visuais podem ser gravadas na memória do ambiente para melhorar futuras buscas. Se preferir, você pode recusar e responder manualmente onde o objeto está.
          </p>
        </div>

        <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 12 }}>
          <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
          <span style={{ color: '#9ca3af' }}>Lembrar permissão (não será solicitado de novo)</span>
        </label>

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 18 }}>
          <button className="btn-screen" onClick={onDeny} style={{ background: 'transparent', color: '#94a3b8', border: '1px solid rgba(148,163,184,0.06)' }}>Recusar</button>
          <button className="btn-screen" disabled={loading} onClick={async () => { setLoading(true); try { await onAllow(remember) } finally { setLoading(false) } }} style={{ background: '#0ea5a4', color: '#021014' }}>{loading ? 'Aguarde...' : 'Permitir e capturar'}</button>
        </div>
      </div>
    </div>
  )
}
