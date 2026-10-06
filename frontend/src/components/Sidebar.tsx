import { type ReactNode, useState } from 'react'

interface Item {
  icon: string
  label: string
  active?: boolean
  onClick: () => void
  title?: string
}

interface Props {
  items: Item[]
  children?: ReactNode
  header?: ReactNode
}

export default function Sidebar({ items, children, header }: Props) {
  const [open, setOpen] = useState(true)

  return (
    <nav className={`toolnav ${open ? 'open' : 'closed'}`}>
      {open && header && <div className="sb-header">{header}</div>}
      <button
        className="sb-toggle"
        onClick={() => setOpen(!open)}
        title={open ? 'Recolher menu' : 'Abrir menu'}
      >
        {open ? '⟨' : '☰'}
      </button>
      <div className="sb-scroll">
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
        {open && children && <div className="sb-extra">{children}</div>}
      </div>
    </nav>
  )
}