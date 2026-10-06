import { useEffect, useState } from 'react'
import {
  clearEnvironmentMemory,
  getPermissionAudit,
  getPermissions,
  setPermission,
  setLocalPin,
  getLocalPin,
  PERMISSION_LABELS,
  type PermissionMap,
} from '../api'

const DANGEROUS: Record<string, string> = {
  mouse_control: 'Controle do mouse dá ao agente poder de mover o cursor e clicar.',
  keyboard_control: 'Controle do teclado dá ao agente poder de digitar e pressionar teclas.',
  command_execution: 'Executar comandos permite que o agente rode comandos no seu computador.',
}

export default function PermissionsPanel() {
  const [perms, setPerms] = useState<PermissionMap>({})
  const [pin, setPin] = useState(getLocalPin())
  const [needsPin, setNeedsPin] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [audit, setAudit] = useState<any[]>([])
  const [clearing, setClearing] = useState(false)

  async function refresh() {
    const [nextPerms, nextAudit] = await Promise.all([getPermissions(), getPermissionAudit(8)])
    setPerms(nextPerms)
    setAudit(nextAudit)
  }

  useEffect(() => {
    void refresh().catch((e: unknown) =>
      setError(e instanceof Error ? e.message : 'Falha ao carregar permissões'),
    )
  }, [])

  async function toggle(name: string) {
    if (name === 'camera' || name === 'screen_capture') return
    setError('')
    const next = !perms[name]
    if (next && DANGEROUS[name] && !getLocalPin()) {
      setNeedsPin(name)
      return
    }
    await doToggle(name, next)
  }

  async function doToggle(name: string, next: boolean) {
    try {
      await setPermission(name, next)
      setPerms((p) => ({ ...p, [name]: next }))
      setNeedsPin(null)
      await refresh()
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      if (msg.includes('PIN')) {
        setNeedsPin(name)
      } else {
        setError(msg)
      }
    }
  }

  function confirmPin() {
    if (!pin) {
      setError('Digite o PIN local para continuar.')
      return
    }
    setLocalPin(pin)
    if (needsPin) {
      const target = needsPin
      setNeedsPin(null)
      doToggle(target, true)
    }
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
              {DANGEROUS[name] && perms[name] && (
                <p className="perm-warn">Ativa agora — confirme que confia no agente.</p>
              )}
            </li>
          )
        })}
      </ul>

      {needsPin && DANGEROUS[needsPin] && (
        <div className="pin-prompt">
          <p>
            Para ativar <strong>{PERMISSION_LABELS[needsPin]}</strong> é preciso o PIN local.
          </p>
          <p className="perm-warn">{DANGEROUS[needsPin]}</p>
          <input
            type="password"
            value={pin}
            placeholder="PIN local (STUDYAGENT_PIN)"
            onChange={(e) => setPin(e.target.value)}
          />
          <button onClick={confirmPin}>Confirmar</button>
          <button onClick={() => setNeedsPin(null)}>Cancelar</button>
        </div>
      )}

      {error && <p className="perm-error">{error}</p>}

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