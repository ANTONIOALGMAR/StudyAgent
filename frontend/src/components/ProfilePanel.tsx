import { useEffect, useState } from 'react'
import {
  getProfile,
  saveProfile,
  getProfileInsights,
  type ProfileInsights,
} from '../api'

export default function ProfilePanel() {
  const [name, setName] = useState('')
  const [grade, setGrade] = useState('')
  const [school, setSchool] = useState('')
  const [prefs, setPrefs] = useState('')
  const [insights, setInsights] = useState<ProfileInsights | null>(null)
  const [loading, setLoading] = useState(true)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    void getProfile()
      .then((p) => {
        setName(p.name || '')
        setGrade(p.grade || '')
        setSchool(p.school || '')
        setPrefs(p.preferences || '')
      })
      .catch(() => {})
    void getProfileInsights()
      .then(setInsights)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  async function handleSave() {
    try {
      await saveProfile(name, grade, school, prefs)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
      const newInsights = await getProfileInsights()
      setInsights(newInsights)
    } catch {}
  }

  if (loading) return <div className="profile"><p className="prof-loading">carregando…</p></div>

  return (
    <div className="profile">
      <h3>👤 Perfil do aluno</h3>

      <div className="prof-form">
        <label className="prof-field">
          <span>Nome</span>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Seu nome" />
        </label>
        <label className="prof-field">
          <span>Série</span>
          <input value={grade} onChange={(e) => setGrade(e.target.value)} placeholder="ex.: 9º ano" />
        </label>
        <label className="prof-field">
          <span>Escola</span>
          <input value={school} onChange={(e) => setSchool(e.target.value)} placeholder="ex.: EMEF" />
        </label>
        <label className="prof-field">
          <span>Preferências</span>
          <input value={prefs} onChange={(e) => setPrefs(e.target.value)} placeholder="ex.: prefiro exercícios abertos" />
        </label>
        <button className="prof-save" onClick={handleSave}>
          {saved ? '✓ salvo!' : '💾 salvar'}
        </button>
      </div>

      {insights && insights.total_topics_studied > 0 && (
        <div className="prof-insights">
          <h4>📈 Análise de aprendizado</h4>
          <p className="prof-stat">
            {insights.total_topics_studied} tema{insights.total_topics_studied > 1 ? 's' : ''} estudado{insights.total_topics_studied > 1 ? 's' : ''}
          </p>

          {insights.weak_topics.length > 0 && (
            <div className="prof-section">
              <span className="prof-label prof-label-weak">⚠ Pontos fracos</span>
              {insights.weak_topics.map((w) => (
                <div key={w.topic} className="prof-row">
                  <span>{w.topic}</span>
                  <span className="prof-pct-bad">{w.avg_percent}%</span>
                </div>
              ))}
            </div>
          )}

          {insights.strong_topics.length > 0 && (
            <div className="prof-section">
              <span className="prof-label prof-label-strong">✓ Pontos fortes</span>
              {insights.strong_topics.map((s) => (
                <div key={s.topic} className="prof-row">
                  <span>{s.topic}</span>
                  <span className="prof-pct-good">{s.avg_percent}%</span>
                </div>
              ))}
            </div>
          )}

          {insights.suggestions.length > 0 && (
            <div className="prof-section">
              <span className="prof-label prof-label-hint">💡 Sugerido revisar</span>
              {insights.suggestions.map((s) => (
                <div key={s.topic} className="prof-row">
                  <span>{s.topic}</span>
                  <span className="prof-pct-warn">{s.avg_percent}%</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
