import { useEffect, useState } from 'react'
import {
  getAchievements,
  getAchievementProgress,
  getTopicStreaks,
  type Achievement,
  type AchievementProgress,
  type TopicStreak,
} from '../api'

export default function AchievementsPanel() {
  const [achievements, setAchievements] = useState<Achievement[]>([])
  const [progress, setProgress] = useState<AchievementProgress | null>(null)
  const [streaks, setStreaks] = useState<TopicStreak[]>([])
  const [loading, setLoading] = useState(true)

  async function loadAll() {
    setLoading(true)
    try {
      const [a, p, s] = await Promise.all([getAchievements(), getAchievementProgress(), getTopicStreaks()])
      setAchievements(a)
      setProgress(p)
      setStreaks(s)
    } catch (err) {
      // ignore failures but keep UI responsive
      console.warn('Failed to load achievements', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadAll()
  }, [])

  async function handleCheckNew() {
    setLoading(true)
    try {
      await checkAchievements()
      // refresh lists after check
      await loadAll()
    } catch (err) {
      console.warn('Failed to check achievements', err)
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <div className="achievements"><p className="ach-loading">carregando…</p></div>

  const earned = achievements.filter((a) => a.earned)
  const locked = achievements.filter((a) => !a.earned)

  return (
    <div className="achievements">
      <h3>🏆 Conquistas</h3>

      <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
        <button className="btn" onClick={() => void loadAll()}>Atualizar</button>
        <button className="btn btn-primary" onClick={() => void handleCheckNew()}>Verificar novas</button>
      </div>

      {progress && (
        <div className="ach-summary">
          <span className="ach-count">{progress.earned}/{progress.total}</span>
          <div className="ach-bar">
            <div className="ach-fill" style={{ width: `${Math.round(100 * progress.earned / progress.total)}%` }} />
          </div>
        </div>
      )}

      {earned.length > 0 && (
        <div className="ach-section">
          <span className="ach-label ach-label-earned">Desbloqueadas</span>
          <div className="ach-grid">
            {earned.map((a) => (
              <div key={a.id} className="ach-card ach-earned">
                <span className="ach-icon">{a.icon}</span>
                <span className="ach-title">{a.title}</span>
                <span className="ach-desc">{a.description}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {locked.length > 0 && (
        <div className="ach-section">
          <span className="ach-label ach-label-locked">Bloqueadas</span>
          <div className="ach-grid">
            {locked.map((a) => {
              const p = progress?.locked.find((l) => l.id === a.id)
              return (
                <div key={a.id} className="ach-card ach-locked">
                  <span className="ach-icon ach-icon-muted">{a.icon}</span>
                  <span className="ach-title">{a.title}</span>
                  {p && (
                    <div className="ach-progress-bar">
                      <div className="ach-progress-fill" style={{ width: `${p.percent}%` }} />
                      <span className="ach-progress-text">{p.current}/{p.target}</span>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {streaks.length > 0 && (
        <div className="ach-section">
          <span className="ach-label ach-label-streak">🔥 Sequências por tema</span>
          {streaks.slice(0, 8).map((s) => (
            <div key={s.topic} className="streak-row">
              <span className="streak-topic">{s.topic}</span>
              <span className="streak-days">
                {s.current_streak > 0 ? `${s.current_streak}d 🔥` : `${s.days_practiced}d total`}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
