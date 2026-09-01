import { useEffect, useState } from 'react'
import { useUserStore } from '../store/userStore'
import {
  getEnhancedDashboard,
  getLeaderboard,
  getProfile,
  getTimeAnalytics,
  getRecommendations,
  type EnhancedDashboard,
  type Leaderboard,
  type TimeAnalytics,
} from '../api'

export default function StatsPanel() {
  const { setProfile } = useUserStore()
  const [data, setData] = useState<EnhancedDashboard | null>(null)
  const [timeData, setTimeData] = useState<TimeAnalytics | null>(null)
  const [lb, setLb] = useState<Leaderboard | null>(null)
  const [recs, setRecs] = useState<{ available_minutes: number; suggestions: { type: string; description: string; priority: string }[] } | null>(null)
  const [minutes, setMinutes] = useState(30)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    void Promise.all([getEnhancedDashboard(), getTimeAnalytics(), getLeaderboard(), getProfile()])
      .then(([d, t, l, p]) => {
        setData(d);
        setTimeData(t);
        setLb(l);

        // Sync with global store — o nome vem do perfil do aluno,
        // não do leaderboard (que não tem campo "name").
        if (l) {
          setProfile({
            name: p?.name || 'Estudante',
            level: l.level,
            xp: l.total_xp,
            streak: d.exercises.streak_days,
            mastery: {} // Will be populated by dashboard data
          })
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [setProfile])

  async function loadRecs() {
    try {
      const r = await getRecommendations(minutes)
      setRecs(r)
    } catch {}
  }

  if (loading) return <div className="stats"><p className="stats-loading">carregando…</p></div>
  if (!data) return <div className="stats"><p className="stats-loading">sem dados</p></div>

  const ex = data.exercises
  const fc = data.flashcards
  const sp = data.study_plans
  const ws = data.weekly_summary
  const err = data.error_summary

  return (
    <div className="stats">
      <h3>📊 Progresso</h3>

      {lb && (
        <div className="level-bar">
          <div className="level-icon">{lb.icon}</div>
          <div className="level-info">
            <div className="level-name">{lb.level}</div>
            <div className="level-xp">{lb.total_xp} XP</div>
            {lb.next_level && (
              <div className="level-progress-container">
                <div className="level-progress-bar" style={{ width: `${lb.progress_percent}%` }} />
                <span className="level-progress-text">{lb.xp_to_next} XP para {lb.next_level}</span>
              </div>
            )}
            {!lb.next_level && <div className="level-max">Nível máximo!</div>}
          </div>
        </div>
      )}

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

      {ws && ws.exercises.count > 0 && (
        <div className="stats-section">
          <h4>📅 Resumo da semana</h4>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-num">{ws.exercises.count}</div>
              <div className="stat-label">Exercícios (7d)</div>
            </div>
            <div className="stat-card">
              <div className="stat-num">{ws.exercises.avg_percent}%</div>
              <div className="stat-label">Média (7d)</div>
            </div>
            <div className="stat-card">
              <div className="stat-num">{ws.study_minutes}min</div>
              <div className="stat-label">Tempo estudado</div>
            </div>
            <div className="stat-card">
              <div className="stat-num">{ws.topics_practiced}</div>
              <div className="stat-label">Temas (7d)</div>
            </div>
            <div className="stat-card">
              <div className="stat-num">{ws.flashcard_reviews}</div>
              <div className="stat-label">Reviews (7d)</div>
            </div>
            {ws.new_errors > 0 && (
              <div className="stat-card stat-warn-card">
                <div className="stat-num">{ws.new_errors}</div>
                <div className="stat-label">Novos erros</div>
              </div>
            )}
          </div>
        </div>
      )}

      {data.mastery_by_subject.length > 0 && (
        <div className="stats-section">
          <h4>🎯 Mastery por tema</h4>
          {data.mastery_by_subject.map((s) => (
            <div key={s.subject} className={`mastery-row mastery-${s.status}`}>
              <span className="mastery-subject">{s.subject}</span>
              <div className="mastery-bar-container">
                <div className="mastery-bar" style={{ width: `${Math.min(100, s.avg_score)}%` }} />
              </div>
              <span className="mastery-score">{Math.round(s.avg_score)}%</span>
            </div>
          ))}
        </div>
      )}

      {err && err.pending_review > 0 && (
        <div className="stats-section">
          <h4>📝 Caderno de erros</h4>
          <div className="stats-grid">
            <div className="stat-card stat-warn-card">
              <div className="stat-num">{err.pending_review}</div>
              <div className="stat-label">Erros pendentes</div>
            </div>
          </div>
          {err.top_error_topics.length > 0 && (
            <div className="stat-hint">
              Temas com mais erros: {err.top_error_topics.map((t) => `${t.topic} (${t.count})`).join(', ')}
            </div>
          )}
        </div>
      )}

      {timeData && timeData.total_sessions > 0 && (
        <div className="stats-section">
          <h4>⏱ Tempo de estudo</h4>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-num">{timeData.total_study_minutes}min</div>
              <div className="stat-label">Total estudado</div>
            </div>
            <div className="stat-card">
              <div className="stat-num">{timeData.avg_session_minutes}min</div>
              <div className="stat-label">Média por sessão</div>
            </div>
            <div className="stat-card">
              <div className="stat-num">{timeData.total_sessions}</div>
              <div className="stat-label">Sessões registradas</div>
            </div>
          </div>
          {timeData.best_hours.length > 0 && (
            <div className="stat-hint">
              🕐 Melhores horários: {timeData.best_hours.map((h) => `${h.hour}h`).join(', ')}
            </div>
          )}
        </div>
      )}

      <div className="stats-section">
        <h4>💡 O que estudar agora</h4>
        <div className="rec-controls">
          <input
            type="number"
            min={5}
            max={120}
            value={minutes}
            onChange={(e) => setMinutes(Math.max(5, Math.min(120, Number(e.target.value) || 30)))}
            className="rec-input"
          />
          <span className="rec-label">minutos disponíveis</span>
          <button className="rec-btn" onClick={loadRecs}>Sugerir</button>
        </div>
        {recs && recs.suggestions.length > 0 && (
          <div className="rec-list">
            {recs.suggestions.map((s, i) => (
              <div key={i} className={`rec-item rec-${s.priority}`}>
                <span className="rec-type">{s.type === 'flashcards' ? '🃏' : s.type === 'exercise' ? '🎯' : s.type === 'study_plan' ? '📋' : '📚'}</span>
                <span className="rec-desc">{s.description}</span>
                <span className={`rec-priority rec-priority-${s.priority}`}>{s.priority}</span>
              </div>
            ))}
          </div>
        )}
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
