import { useState } from 'react'

interface Item {
  icon: string
  label: string
  active?: boolean
  onClick: () => void
  title?: string
}

interface Props {
  items: Item[]
}

export default function Sidebar({ items }: Props) {
  const [open, setOpen] = useState(true)

  return (
    <nav className={`toolnav ${open ? 'open' : 'closed'}`}>
      <button
        className="sb-toggle"
        onClick={() => setOpen(!open)}
        title={open ? 'Recolher menu' : 'Abrir menu'}
      >
        {open ? '⟨' : '☰'}
      </button>
      <ul className="sb-list">
        {items.map((item) => (
          <li key={item.label}>
            <button
              className={`sb-item ${item.active ? 'active' : ''}`}
              onClick={item.onClick}
              title={item.title || item.label}
            >
              <span className="sb-icon">{item.icon}</span>
              {open && (
                <span className="sb-label">
                  {item.label}
                  {item.active && <span className="sb-on">ativo</span>}
                </span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  )
}
