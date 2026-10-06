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
          aria-label="Selecionar monitor"
        >
{/* -1 = desktop virtual completo (todas as telas combinadas). */}
          <option value={-1} title="Captura do desktop virtual que combina todas as telas conectadas">Todas as telas (desktop virtual)</option>

          {/* Monitores físicos na ordem do xrandr (0..n). */}
          {monitors.map((m) => (
            <option key={m.index} value={m.index} title={`Tela ${m.index}${m.name ? ` (${m.name})` : ''}: ${m.width}×${m.height}`}>
              Tela {m.index} · {m.name ? `${m.name} · ` : ''}{m.width}×{m.height}
            </option>
          ))}
        </select>

        {/* Small inline tooltip icon explaining the virtual desktop option */}
        <span
          role="img"
          aria-label="Informação sobre todas as telas"
          title="'Todas as telas (desktop virtual)' captura o desktop combinado (uma única imagem que cobre todo o espaço virtual). Use esta opção para analisar o conteúdo que pode estar distribuído em múltiplos monitores."
          style={{ marginLeft: 8, color: '#94a3b8', cursor: 'default' }}
        >
          ℹ️
        </span>
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
