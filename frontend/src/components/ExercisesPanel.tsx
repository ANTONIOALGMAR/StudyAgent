import { useState } from 'react'
import {
  generateExercises,
  generateAdaptiveExercises,
  generateReviewExercises,
  gradeExercise,
  type ExerciseSet,
  type GradeResult,
} from '../api'

const LEVELS = [
  { id: 'ensino fundamental', label: 'Básico' },
  { id: 'ensino médio', label: 'Médio' },
  { id: 'aberta', label: 'Dissertativas' },
]

interface Props {
  onMood: (mood: 'happy' | 'concerned' | 'curious' | null) => void
}

export default function ExercisesPanel({ onMood }: Props) {
  const [topic, setTopic] = useState('')
  const [n, setN] = useState(4)
  const [level, setLevel] = useState(LEVELS[0].id)
  const [exercise, setExercise] = useState<ExerciseSet | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [result, setResult] = useState<GradeResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleGenerate() {
    if (!topic.trim() || loading) return
    setLoading(true)
    setError(null)
    try {
      const ex = await generateExercises(topic.trim(), n, level)
      setExercise(ex)
      setAnswers({})
      setResult(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  async function handleAdaptive() {
    if (!topic.trim() || loading) return
    setLoading(true)
    setError(null)
    try {
      const ex = await generateAdaptiveExercises(topic.trim(), n)
      setExercise(ex)
      setAnswers({})
      setResult(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  async function handleReview() {
    if (loading) return
    setLoading(true)
    setError(null)
    try {
      const ex = await generateReviewExercises(n)
      if (!ex.exercise_id) {
        setError(ex.message || 'Nada para revisar')
        setLoading(false)
        return
      }
      setExercise(ex)
      setAnswers({})
      setResult(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  async function handleSubmit() {
    if (!exercise || loading) return
    setLoading(true)
    setError(null)
    try {
      const r = await gradeExercise(exercise.exercise_id, answers)
      setResult(r)
      onMood(r.percent >= 70 ? 'happy' : r.percent >= 40 ? 'concerned' : 'concerned')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  function setAnswer(qid: string, value: string, option?: string) {
    setAnswers((a) => ({ ...a, [qid]: option ?? value }))
  }

  return (
    <div className="exercises">
      {!exercise && (
        <div className="exercises-form">
          <input
            className="ex-topic"
            placeholder="Tema (ex.: frações, equações do 1º grau…)"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
          />
          <div className="ex-controls">
            <select value={level} onChange={(e) => setLevel(e.target.value)}>
              {LEVELS.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.label}
                </option>
              ))}
            </select>
            <label className="ex-count">
              Questões:
              <input
                type="number"
                min={1}
                max={8}
                value={n}
                onChange={(e) =>
                  setN(Math.max(1, Math.min(8, Number(e.target.value) || 4)))
                }
              />
            </label>
            <button onClick={handleGenerate} disabled={!topic.trim() || loading}>
              {loading ? 'Gerando…' : '🎯 Gerar'}
            </button>
            <button onClick={handleAdaptive} disabled={!topic.trim() || loading} title="Dificuldade adaptativa baseada no seu histórico">
              🧠 Adaptativo
            </button>
            <button onClick={handleReview} disabled={loading} title="Revisar erros do caderno">
              📝 Revisão
            </button>
          </div>
          {error && <p className="ex-error">{error}</p>}
        </div>
      )}

      {exercise && (
        <div className="ex-quiz">
          <h3>🎯 {exercise.topic}</h3>

          {exercise.questions.map((q, i) => {
            const item = result?.results.find((r) => r.id === q.id)
            return (
              <div
                key={q.id}
                className={`ex-question ${item ? (item.correct ? 'correct' : 'wrong') : ''}`}
              >
                <p className="ex-q-text">
                  <strong>{i + 1}.</strong> {q.q}
                  {item && (
                    <span className="ex-mark">{item.correct ? ' ✓' : ' ✗'}</span>
                  )}
                </p>
                {q.options ? (
                  <div className="ex-options">
                    {q.options.map((opt) => (
                      <button
                        key={opt}
                        className={`ex-option ${answers[q.id] === opt ? 'selected' : ''}`}
                        disabled={!!result}
                        onClick={() => setAnswer(q.id, '', opt)}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                ) : (
                  <input
                    className="ex-answer"
                    placeholder="Sua resposta…"
                    value={answers[q.id] || ''}
                    disabled={!!result}
                    onChange={(e) => setAnswer(q.id, e.target.value)}
                    onKeyDown={(e) =>
                      e.key === 'Enter' && !result && handleSubmit()
                    }
                  />
                )}
                {item && !item.correct && (
                  <p className="ex-feedback">
                    Gabarito: <strong>{item.expected}</strong> — {item.explanation}
                  </p>
                )}
                {item && item.correct && item.explanation && (
                  <p className="ex-feedback ok">💡 {item.explanation}</p>
                )}
              </div>
            )
          })}

          {!result && (
            <button
              className="ex-submit"
              onClick={handleSubmit}
              disabled={loading || Object.keys(answers).length === 0}
            >
              {loading ? 'Corrigindo…' : '✅ Corrigir'}
            </button>
          )}

          {result && (
            <div className="ex-result">
              <div className="ex-scorebar">
                <div
                  className="ex-scorefill"
                  style={{ width: `${result.percent}%` }}
                />
                <span>
                  {result.score}/{result.total} · {result.percent}%
                </span>
              </div>
              <p>{result.message}</p>
              <div className="ex-actions">
                <button
                  onClick={() => {
                    setExercise(null)
                    setResult(null)
                    setAnswers({})
                  }}
                >
                  🔄 Novos exercícios
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
