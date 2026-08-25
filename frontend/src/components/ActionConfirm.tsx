import { useEffect, useState } from 'react'
import {
  getPendingActions,
  approveAction,
  rejectAction,
  type ActionProposal,
} from '../api'

export default function ActionConfirm() {
  const [proposals, setProposals] = useState<ActionProposal[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    void refresh()
  }, [])

  async function refresh() {
    try {
      const pending = await getPendingActions()
      setProposals(pending)
    } catch {}
    setLoading(false)
  }

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

  if (loading || proposals.length === 0) return null

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
