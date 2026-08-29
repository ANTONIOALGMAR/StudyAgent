import { useState } from 'react'
import type { Agent3DState } from '../components/StudyAgent3D/agentStates'

export type { Agent3DState }

export interface UseAgentState {
  state: Agent3DState
  setState: (s: Agent3DState) => void
}

export function useAgentState(initial: Agent3DState = 'idle'): UseAgentState {
  const [state, setState] = useState<Agent3DState>(initial)
  return { state, setState }
}
