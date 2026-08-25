import { useEffect, useState } from 'react'
import { getDashboard, type Dashboard } from '../api'

export default function StatsPanel() {
  const [data, setData] = useState<Dashboard | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    void getDashboard()
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="stats"><p className="stats-loading">carregando…</p></div>
  if (!data) return <div className="stats"><p className="stats-loading">sem dados</p></div>

  const ex = data.exercises
  const fc = data.flashcards
  const sp = data.study_plans

  return (
    <div className="stats">
      <h3>📊 Progresso</h3>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-num">{ex.total_sessions}</div>
          <div className="stat-label">Exercícios feitos</div>
        </div>
        <div className="stat-card">
          <div className="stat-num">{ex.avg_percent}%</div>
          <div className="stat-label">Média geral</div>
        </div>
        <div className="stat-card">
          <div className="stat-num">{ex.streak_days}d</div>
          <div className="stat-label">Sequência</div>
        </div>
        <div className="stat-card">
          <div className="stat-num">{fc.total_cards}</div>
          <div className="stat-label">Flashcards</div>
        </div>
        <div className="stat-card">
          <div className="stat-num">{fc.mastered}</div>
          <div className="stat-label">Dominados</div>
        </div>
        <div className="stat-card">
          <div className="stat-num">{sp.overall_percent}%</div>
          <div className="stat-label">Planos concluídos</div>
        </div>
      </div>

      {ex.recent.length > 0 && (
        <div className="stats-section">
          <h4>🎯 Últimos exercícios</h4>
          {ex.recent.map((r, i) => (
            <div key={i} className="stat-row">
              <span>{r.topic}</span>
              <span className={r.percent >= 70 ? 'stat-ok' : 'stat-warn'}>
                {r.score}/{r.total} ({r.percent}%)
              </span>
            </div>
          ))}
        </div>
      )}

      {sp.plans.length > 0 && (
        <div className="stats-section">
          <h4>📋 Planos ativos</h4>
          {sp.plans.map((p) => (
            <div key={p.id} className="stat-row">
              <span>{p.title}</span>
              <span>{p.done_items}/{p.total_items} ({p.percent}%)</span>
            </div>
          ))}
        </div>
      )}

      {fc.due_now > 0 && (
        <div className="stats-hint">
          🃏 {fc.due_now} card{fc.due_now > 1 ? 's' : ''} aguardando revisão
        </div>
      )}
    </div>
  )
}
