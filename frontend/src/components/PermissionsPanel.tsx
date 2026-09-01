import { useEffect, useState } from 'react'
import { getPermissions, setPermission, PERMISSION_LABELS, type PermissionMap } from '../api'

export default function PermissionsPanel() {
  const [perms, setPerms] = useState<PermissionMap>({})

  useEffect(() => {
    getPermissions().then(setPerms)
  }, [])

  async function toggle(name: string) {
    if (name === 'camera' || name === 'screen_capture') return
    const next = !perms[name]
    await setPermission(name, next)
    setPerms((p) => ({ ...p, [name]: next }))
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
    </div>
  )
}
