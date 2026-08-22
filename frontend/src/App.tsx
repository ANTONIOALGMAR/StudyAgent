import Chat from './components/Chat'
import PermissionsPanel from './components/PermissionsPanel'

export default function App() {
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="logo">
          🎓 StudyAgent
          <span className="subtitle">tutor local · privado</span>
        </div>
        <PermissionsPanel />
      </aside>
      <main className="main">
        <Chat />
      </main>
    </div>
  )
}
