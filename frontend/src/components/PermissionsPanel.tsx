import { useEffect, useState } from 'react'
import { getPermissions, setPermission, PERMISSION_LABELS, type PermissionMap } from '../api'

export default function PermissionsPanel() {
  const [perms, setPerms] = useState<PermissionMap>({})

  useEffect(() => {
    getPermissions().then(setPerms)
  }, [])

  async function toggle(name: string) {
    const next = !perms[name]
    await setPermission(name, next)
    setPerms((p) => ({ ...p, [name]: next }))
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
          </li>
        ))}
      </ul>
    </div>
  )
}
