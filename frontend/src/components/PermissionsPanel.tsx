import { useEffect, useState } from 'react'
import { clearEnvironmentMemory, getPermissionAudit, getPermissions, setPermission, PERMISSION_LABELS, type PermissionMap } from '../api'

export default function PermissionsPanel() {
  const [perms, setPerms] = useState<PermissionMap>({})
  const [audit, setAudit] = useState<any[]>([])
  const [clearing, setClearing] = useState(false)

  async function refresh() {
    const [nextPerms, nextAudit] = await Promise.all([getPermissions(), getPermissionAudit(8)])
    setPerms(nextPerms)
    setAudit(nextAudit)
  }

  useEffect(() => {
    void refresh()
  }, [])

  async function toggle(name: string) {
    if (name === 'camera' || name === 'screen_capture') return
    const next = !perms[name]
    await setPermission(name, next)
    setPerms((p) => ({ ...p, [name]: next }))
    await refresh()
  }

  async function handleClearMemory() {
    setClearing(true)
    try {
      const result = await clearEnvironmentMemory({ all: true })
      window.alert(`Memória do ambiente limpa: ${result.deleted} registros removidos.`)
      await refresh()
    } catch (err) {
      console.error(err)
      window.alert('Não foi possível limpar a memória do ambiente.')
    } finally {
      setClearing(false)
    }
  }

  return (
    <div className="permissions">
      <h3>Permissões</h3>
      <ul>
        {Object.keys(PERMISSION_LABELS).map((name) => {
          const alwaysOn = name === 'camera' || name === 'screen_capture'
          return (
            <li key={name}>
              <button
                className={`perm ${perms[name] ? 'on' : 'off'}`}
                onClick={() => toggle(name)}
                disabled={alwaysOn}
                title={alwaysOn ? 'Sempre ativa para identificação e ambiente' : undefined}
                style={alwaysOn ? { opacity: 1, cursor: 'default' } : undefined}
              >
                <span className="dot">{perms[name] ? '●' : '○'}</span>
                {PERMISSION_LABELS[name]}{alwaysOn ? ' • fixa' : ''}
              </button>
            </li>
          )
        })}
      </ul>

      <div style={{ marginTop: 14, display: 'grid', gap: 8 }}>
        <button className="btn-screen" onClick={handleClearMemory} disabled={clearing}>
          {clearing ? 'Limpando...' : '🧹 limpar memória do ambiente'}
        </button>
      </div>

      <div style={{ marginTop: 18 }}>
        <strong style={{ display: 'block', marginBottom: 8 }}>Auditoria recente</strong>
        {audit.length === 0 ? (
          <div style={{ color: '#94a3b8', fontSize: 12 }}>Sem eventos registrados.</div>
        ) : (
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: 6 }}>
            {audit.map((entry, idx) => (
              <li key={`${entry.action}-${entry.permission}-${idx}`} style={{ background: 'rgba(15,23,42,0.6)', border: '1px solid rgba(148,163,184,0.2)', borderRadius: 8, padding: '6px 8px', fontSize: 11, color: '#cbd5e1' }}>
                <div style={{ fontWeight: 600 }}>{entry.permission || 'permissão'} · {entry.action}</div>
                <div>{entry.reason || 'sem motivo informado'}</div>
                {entry.actor && <div style={{ color: '#93c5fd' }}>actor: {entry.actor}</div>}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
