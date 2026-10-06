import { useEffect, useState } from 'react'
import {
  getPendingActions,
  approveAction,
  rejectAction,
  type ActionProposal,
} from '../api'

const POLL_MS = 5000

export default function ActionConfirm() {
  const [proposals, setProposals] = useState<ActionProposal[]>([])

  // Poll das ações pendentes: o agente propõe ações durante a conversa e, sem
  // isso, novas propostas só apareceriam depois de um reload da página.
  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const pending = await getPendingActions()
        if (alive) setProposals(pending)
      } catch {
        // Backend fora do ar / rate limit — tenta de novo no próximo ciclo.
      }
    }
    void tick()
    const timer = setInterval(() => void tick(), POLL_MS)
    return () => {
      alive = false
      clearInterval(timer)
    }
  }, [])

  async function handleApprove(id: string) {
    try {
      await approveAction(id)
      setProposals((p) => p.filter((x) => x.id !== id))
    } catch {}
  }

  async function handleReject(id: string) {
    try {
      await rejectAction(id)
      setProposals((p) => p.filter((x) => x.id !== id))
    } catch {}
  }

  if (proposals.length === 0) return null

  return (
    <div className="action-confirm-bar">
      {proposals.map((p) => (
        <div key={p.id} className="action-proposal">
          <span className="action-label">
            {p.label || p.action_type}: {p.description || 'ação proposta'}
          </span>
          <div className="action-buttons">
            <button className="action-approve" onClick={() => handleApprove(p.id)}>
              ✓ executar
            </button>
            <button className="action-reject" onClick={() => handleReject(p.id)}>
              ✕ recusar
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
