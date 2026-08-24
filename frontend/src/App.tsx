import { useState } from 'react'
import Chat from './components/Chat'
import PermissionsPanel from './components/PermissionsPanel'

export default function App() {
  const [permOpen, setPermOpen] = useState(true)

  return (
    <div className="app">
      <aside className={`sidebar ${permOpen ? 'perms-open' : 'perms-collapsed'}`}>
        <button
          className="ps-toggle"
          onClick={() => setPermOpen(!permOpen)}
          title={permOpen ? 'Ocultar painel' : 'Abrir painel'}
        >
          {permOpen ? '⟨' : '🎓'}
        </button>
        {permOpen && (
          <>
            <div className="logo">
              🎓 StudyAgent
              <span className="subtitle">tutor local · privado</span>
            </div>
            <PermissionsPanel />
          </>
        )}
      </aside>
      <main className="main">
        <Chat />
      </main>
    </div>
  )
}
