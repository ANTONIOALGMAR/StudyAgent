import { useEffect, useState } from 'react'
import {
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

  useEffect(() => {
    getPermissions().then(setPerms)
  }, [])

  async function toggle(name: string) {
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

  return (
    <div className="permissions">
      <h3>Permissões</h3>
      <ul>
        {Object.keys(PERMISSION_LABELS).map((name) => (
          <li key={name}>
            <button
              className={`perm ${perms[name] ? 'on' : 'off'}`}
              onClick={() => toggle(name)}
            >
              <span className="dot">{perms[name] ? '●' : '○'}</span>
              {PERMISSION_LABELS[name]}
            </button>
            {DANGEROUS[name] && perms[name] && (
              <p className="perm-warn">Ativa agora — confirme que confia no agente.</p>
            )}
          </li>
        ))}
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
    </div>
  )
}