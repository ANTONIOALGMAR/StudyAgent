import type { Agent3DState } from '../agentStates'

export interface AgentAnimationTargets {
  headRotY: number
  headRotX: number
  lookX: number
  lookY: number
  blink: boolean
  mouthOpen: number
  brow: number
  lean: number
}

const TARGETS: Record<string, Partial<AgentAnimationTargets>> = {
  idle: {},
  listening: { headRotY: 0.06, lookX: 0.1, mouthOpen: 0.2, lean: 0.04 },
  recording: { headRotY: -0.05, lookX: -0.08, mouthOpen: 0.3 },
  thinking: { headRotX: -0.18, lookY: 0.3, brow: 0.35, lean: 0.1 },
  speaking: { headRotY: 0.05, mouthOpen: 0.6 },
  error: { headRotX: 0.12, headRotY: 0.14, brow: -0.3, lean: -0.08 },
  happy: { headRotY: 0.22, headRotX: -0.05, mouthOpen: 0.4, lean: 0.06 },
  concerned: { headRotX: -0.1, headRotY: -0.08, brow: 0.4 },
  curious: { headRotX: 0.12, headRotY: -0.14, lookY: -0.2, brow: 0.28 },
  excited: { headRotY: 0.28, headRotX: -0.02, mouthOpen: 0.5, brow: 0.2, lean: 0.08 },
  confused: { headRotX: 0.12, headRotY: 0.18, lookX: -0.2, brow: 0.45, lean: -0.06 },
  sleeping: { headRotX: -0.35, lookY: -0.3, lean: 0.15, blink: true },
}

/**
 * Pure function of (state, time). Deterministic per frame, so every
 * sub-component that calls it inside useFrame stays in sync.
 */
export function computeAgentAnimation(state: Agent3DState, t: number): AgentAnimationTargets {
  const base = TARGETS[state] ?? {}

  const idleBreathe = Math.sin(t * 1.4) * 0.012
  const idleRock = Math.sin(t * 0.7) * 0.05
  const idleBlink = state === 'idle' && Math.sin(t * 0.6) > 0.99

  const mouthPulse =
    Math.abs(Math.sin(t * 4.2)) * 0.06 * (state === 'speaking' ? 1.6 : 0.5)

  return {
    headRotY: (base.headRotY ?? 0) + idleRock,
    headRotX: (base.headRotX ?? 0) + idleBreathe,
    lookX: base.lookX ?? 0,
    lookY: base.lookY ?? 0,
    blink: base.blink ?? idleBlink,
    mouthOpen: Math.min(1, (base.mouthOpen ?? 0) + mouthPulse),
    brow: base.brow ?? 0,
    lean: base.lean ?? 0,
  }
}
