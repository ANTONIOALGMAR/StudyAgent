import { useState } from 'react'
import {
  generateFlashcards,
  getFlashcardDecks,
  getDueCards,
  reviewFlashcard,
  flashcardDeckStats,
  exportDeckCsvUrl,
  importFlashcards,
  type FlashcardDeck,
  type Flashcard,
} from '../api'

interface Props {
  onMood: (mood: 'happy' | 'concerned' | 'curious' | null) => void
}

export default function FlashcardsPanel({ onMood }: Props) {
  const [topic, setTopic] = useState('')
  const [n, setN] = useState(10)
  const [level, setLevel] = useState('ensino fundamental')
  const [decks, setDecks] = useState<FlashcardDeck[]>([])
  const [activeDeckId, setActiveDeckId] = useState<string | null>(null)
  const [dueCards, setDueCards] = useState<Flashcard[]>([])
  const [currentIdx, setCurrentIdx] = useState(0)
  const [showBack, setShowBack] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [stats, setStats] = useState<{ total: number; due: number; learned: number } | null>(null)
  const [importOpen, setImportOpen] = useState(false)
  const [importText, setImportText] = useState('')
  const [importTopic, setImportTopic] = useState('')

  async function loadDecks() {
    try {
      const d = await getFlashcardDecks()
      setDecks(d)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  async function handleGenerate() {
    if (!topic.trim() || loading) return
    setLoading(true)
    setError(null)
    try {
      await generateFlashcards(topic.trim(), n, level)
      await loadDecks()
      setTopic('')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  async function startReview(deckId: string) {
    setLoading(true)
    setError(null)
    try {
      const cards = await getDueCards(deckId)
      const st = await flashcardDeckStats(deckId)
      setActiveDeckId(deckId)
      setDueCards(cards)
      setStats(st)
      setCurrentIdx(0)
      setShowBack(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  async function handleReview(difficulty: string) {
    const card = dueCards[currentIdx]
    if (!card || loading) return
    setLoading(true)
    try {
      await reviewFlashcard(card.id, difficulty)
      if (currentIdx + 1 < dueCards.length) {
        setCurrentIdx(currentIdx + 1)
        setShowBack(false)
      } else {
        // review complete
        setActiveDeckId(null)
        setDueCards([])
        await loadDecks()
        onMood('happy')
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  if (activeDeckId && dueCards.length > 0 && currentIdx < dueCards.length) {
    const card = dueCards[currentIdx]
    return (
      <div className="flashcards">
        <div className="fc-review">
          <div className="fc-progress">
            {currentIdx + 1} / {dueCards.length}
            {stats && <span className="fc-stats-label"> · {stats.learned} dominados</span>}
          </div>
          <div className={`fc-card ${showBack ? 'flipped' : ''}`} onClick={() => setShowBack(!showBack)}>
            <div className="fc-front">{card.front}</div>
            {showBack && <div className="fc-back">{card.back}</div>}
          </div>
          {!showBack ? (
            <button className="fc-reveal" onClick={() => setShowBack(true)}>
              Revelar resposta
            </button>
          ) : (
            <div className="fc-buttons">
              <button className="fc-btn fc-again" onClick={() => handleReview('again')} disabled={loading}>
                😵 De novo
              </button>
              <button className="fc-btn fc-hard" onClick={() => handleReview('hard')} disabled={loading}>
                😓 Difícil
              </button>
              <button className="fc-btn fc-good" onClick={() => handleReview('good')} disabled={loading}>
                😊 Bom
              </button>
              <button className="fc-btn fc-easy" onClick={() => handleReview('easy')} disabled={loading}>
                🤩 Fácil
              </button>
            </div>
          )}
          <button className="fc-skip" onClick={() => { setActiveDeckId(null); setDueCards([]) }}>
            ✕ encerrar revisão
          </button>
        </div>
      </div>
    )
  }

  function handleExportCsv(deckId: string) {
    const url = exportDeckCsvUrl(deckId)
    const a = document.createElement('a')
    a.href = url
    a.download = `deck_${deckId}.csv`
    a.click()
  }

  async function handleImport() {
    if (!importText.trim()) return
    setLoading(true)
    try {
      await importFlashcards(importText, importTopic || 'Importado', importTopic || 'Importado')
      setImportText('')
      setImportTopic('')
      setImportOpen(false)
      await loadDecks()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  if (activeDeckId && dueCards.length === 0) {
    return (
      <div className="flashcards">
        <p className="fc-done">Nenhum card para revisar agora! Volte mais tarde.</p>
        <button className="fc-back-btn" onClick={() => { setActiveDeckId(null); loadDecks() }}>
          ← voltar
        </button>
      </div>
    )
  }

  return (
    <div className="flashcards">
      {!decks.length && (
        <div className="fc-form">
          <input
            className="fc-topic"
            placeholder="Tema (ex.: fotossíntese, Revolução Francesa…)"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
          />
          <div className="fc-controls">
            <select value={level} onChange={(e) => setLevel(e.target.value)}>
              <option value="ensino fundamental">Básico</option>
              <option value="ensino médio">Médio</option>
            </select>
            <label className="fc-count">
              Cards:
              <input
                type="number"
                min={3}
                max={25}
                value={n}
                onChange={(e) => setN(Math.max(3, Math.min(25, Number(e.target.value) || 10)))}
              />
            </label>
            <button onClick={handleGenerate} disabled={!topic.trim() || loading}>
              {loading ? 'Gerando…' : '🃏 Gerar'}
            </button>
          </div>
          {error && <p className="fc-error">{error}</p>}
        </div>
      )}

      {decks.length > 0 && (
        <div className="fc-decks">
          <h3>📦 Baralhos</h3>
          {decks.map((d) => (
            <div key={d.id} className="fc-deck">
              <div className="fc-deck-info">
                <strong>{d.topic}</strong>
                <span>{d.card_count} cards</span>
              </div>
              <div className="fc-deck-actions">
                <button
                  className="fc-review-btn"
                  onClick={() => startReview(d.id)}
                  disabled={loading}
                >
                  📖 Revisar
                </button>
                <button
                  className="fc-export-btn"
                  onClick={() => handleExportCsv(d.id)}
                  title="Exportar CSV"
                >
                  📥
                </button>
              </div>
            </div>
          ))}
          <div className="fc-new">
            <button onClick={() => setDecks([])} className="fc-new-btn">
              + novo baralho
            </button>
            <button onClick={() => setImportOpen(!importOpen)} className="fc-new-btn">
              📤 importar CSV
            </button>
          </div>
          {importOpen && (
            <div className="fc-import">
              <input
                className="fc-topic"
                placeholder="Tema dos cards importados"
                value={importTopic}
                onChange={(e) => setImportTopic(e.target.value)}
              />
              <textarea
                className="fc-import-text"
                placeholder="Cole o CSV aqui (front TAB back, um card por linha)"
                value={importText}
                onChange={(e) => setImportText(e.target.value)}
                rows={6}
              />
              <button onClick={handleImport} disabled={!importText.trim() || loading}>
                {loading ? 'Importando…' : '📤 importar'}
              </button>
            </div>
          )}
        </div>
      )}

      {error && <p className="fc-error">{error}</p>}
    </div>
  )
}
