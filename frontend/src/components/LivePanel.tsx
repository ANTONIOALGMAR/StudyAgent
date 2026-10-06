import type { MonitorInfo } from '../api'
import { screenPreviewUrl } from '../api'

interface Props {
  monitors: MonitorInfo[]
  monitorSel: number
  setMonitorSel: (v: number) => void
  previewTick: number
  watchMode: boolean
  setWatchMode: (v: boolean) => void
  autoSolve: boolean
  setAutoSolve: (v: boolean) => void
  onClose: () => void
  onMinimize: () => void
}

export default function LivePanel({
  monitors, monitorSel, setMonitorSel,
  previewTick, watchMode, setWatchMode,
  autoSolve, setAutoSolve,
  onClose, onMinimize,
}: Props) {
  return (
    <div className="live-panel">
      <div className="live-head">
        <span className="live-dot" />
        <strong>ao vivo</strong>
        <select
          value={monitorSel}
          onChange={(e) => setMonitorSel(Number(e.target.value))}
        >
          {monitors.length === 0 && <option value={0}>Tela 1</option>}
          {monitors.map((m) => (
            <option key={m.index} value={m.index}>
              Tela {m.index + 1} · {m.width}×{m.height}
            </option>
          ))}
        </select>
        <button className="btn-screen" onClick={onMinimize} title="Minimizar">—</button>
        <button className="btn-screen" onClick={onClose}>✕</button>
      </div>
      <img
        key={previewTick}
        src={screenPreviewUrl(monitorSel)}
        alt="tela ao vivo"
        className="live-img"
      />
      <label className="watch-toggle">
        <input
          type="checkbox"
          checked={watchMode}
          onChange={(e) => setWatchMode(e.target.checked)}
        />
        agente comenta mudanças automaticamente
      </label>
      <label className="watch-toggle" title="Varre a tela a cada 5s e resolve sozinho as questões que aparecerem (uma vez cada)">
        <input
          type="checkbox"
          checked={autoSolve}
          onChange={(e) => setAutoSolve(e.target.checked)}
        />
        🧩 resolver questões automaticamente
      </label>
    </div>
  )
}
