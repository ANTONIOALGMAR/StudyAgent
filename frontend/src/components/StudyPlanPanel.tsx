import { useState } from 'react'
import {
  generateStudyPlan,
  getStudyPlans,
  getStudyPlan,
  toggleStudyItem,
  studyPlanExportUrl,
  type StudyPlan,
  type StudyItem,
} from '../api'

interface Props {
  onMood: (mood: 'happy' | 'concerned' | 'curious' | null) => void
}

export default function StudyPlanPanel({ onMood }: Props) {
  const [topic, setTopic] = useState('')
  const [level, setLevel] = useState('ensino fundamental')
  const [plans, setPlans] = useState<StudyPlan[]>([])
  const [activePlan, setActivePlan] = useState<StudyPlan | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function loadPlans() {
    try {
      const p = await getStudyPlans()
      setPlans(p)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  async function handleGenerate() {
    if (!topic.trim() || loading) return
    setLoading(true)
    setError(null)
    try {
      const plan = await generateStudyPlan(topic.trim(), level)
      setActivePlan(plan)
      setTopic('')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  async function openPlan(planId: string) {
    setLoading(true)
    try {
      const plan = await getStudyPlan(planId)
      setActivePlan(plan)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  async function handleToggle(itemId: number) {
    try {
      const result = await toggleStudyItem(itemId)
      if (activePlan) {
        setActivePlan({
          ...activePlan,
          done_items: result.done_items,
          total_items: result.total_items,
          items: (activePlan.items ?? []).map((it: StudyItem) =>
            it.id === itemId ? { ...it, done: result.done ? 1 : 0 } : it
          ),
        })
        if (result.done_items === result.total_items && result.total_items > 0) {
          onMood('happy')
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  function handleExportPlan(planId: string) {
    const url = studyPlanExportUrl(planId)
    const a = document.createElement('a')
    a.href = url
    a.download = `plano_${planId}.json`
    a.click()
  }

  if (activePlan) {
    const pct = Math.round((activePlan.done_items / Math.max(activePlan.total_items, 1)) * 100)
    return (
      <div className="study-plan">
        <div className="sp-header">
          <button className="sp-back" onClick={() => { setActivePlan(null); void loadPlans() }}>
            ←
          </button>
          <div>
            <h3>📋 {activePlan.title}</h3>
            <span className="sp-topic">{activePlan.topic}</span>
          </div>
          <div className="sp-pct">{pct}%</div>
          <button
            className="sp-export-btn"
            onClick={() => handleExportPlan(activePlan.id)}
            title="Exportar plano"
          >
            📥
          </button>
        </div>
        <div className="sp-bar">
          <div className="sp-fill" style={{ width: `${pct}%` }} />
        </div>
        <div className="sp-items">
          {(activePlan.items ?? []).map((it: StudyItem) => (
            <label key={it.id} className={`sp-item ${it.done ? 'done' : ''}`}>
              <input
                type="checkbox"
                checked={!!it.done}
                onChange={() => handleToggle(it.id)}
              />
              <div>
                <span className="sp-item-title">{it.title}</span>
                {it.detail && <span className="sp-item-detail">{it.detail}</span>}
              </div>
            </label>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="study-plan">
      {!plans.length && !loading && (
        <div className="sp-form">
          <input
            className="sp-topic-input"
            placeholder="Tema (ex.: mitochondria, equações do 2º grau…)"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
          />
          <div className="sp-controls">
            <select value={level} onChange={(e) => setLevel(e.target.value)}>
              <option value="ensino fundamental">Básico</option>
              <option value="ensino médio">Médio</option>
            </select>
            <button onClick={handleGenerate} disabled={!topic.trim() || loading}>
              {loading ? 'Montando…' : '📋 Gerar plano'}
            </button>
          </div>
          {error && <p className="sp-error">{error}</p>}
        </div>
      )}

      {plans.length > 0 && (
        <div className="sp-list">
          <h3>📋 Planos de estudo</h3>
          {plans.map((p) => {
            const pct = Math.round((p.done_items / Math.max(p.total_items, 1)) * 100)
            return (
              <div key={p.id} className="sp-plan" onClick={() => void openPlan(p.id)}>
                <div className="sp-plan-info">
                  <strong>{p.title}</strong>
                  <span>{p.done_items}/{p.total_items} itens · {pct}%</span>
                </div>
                <div className="sp-mini-bar">
                  <div className="sp-fill" style={{ width: `${pct}%` }} />
                </div>
              </div>
            )
          })}
          <button className="sp-new-btn" onClick={() => setPlans([])}>
            + novo plano
          </button>
        </div>
      )}

      {error && <p className="sp-error">{error}</p>}
    </div>
  )
}
