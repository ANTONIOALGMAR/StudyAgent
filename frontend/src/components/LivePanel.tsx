import type { MonitorInfo } from '../api'
import { screenPreviewUrl } from '../api'

interface Props {
  monitors: MonitorInfo[]
  monitorSel: number
  setMonitorSel: (v: number) => void
  previewTick: number
  watchMode: boolean
  setWatchMode: (v: boolean) => void
  onClose: () => void
  onMinimize: () => void
}

export default function LivePanel({
  monitors, monitorSel, setMonitorSel,
  previewTick, watchMode, setWatchMode,
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
          {monitors.length === 0 && <option value={0}>Todas as telas</option>}
          {monitors.map((m) =>
            m.index === 0 ? (
              <option key={m.index} value={m.index}>
                Todas as telas
              </option>
            ) : (
              <option key={m.index} value={m.index}>
                Tela {m.index} · {m.width}×{m.height}
              </option>
            ),
          )}
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
    </div>
  )
}
