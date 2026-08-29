import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import type { Mesh } from 'three'
import type { Agent3DState } from './agentStates'
import { AGENT3D_STYLES } from './agentStates'
import { computeAgentAnimation } from './animations/useAgentAnimation'
import { getVoiceLevel } from '../../lib/audioReactive'

interface Props {
  state: Agent3DState
  voice?: boolean
}

const MOUTH: Record<Agent3DState, { smile: number; width: number }> = {
  idle: { smile: 0, width: 1 },
  listening: { smile: 0, width: 1 },
  recording: { smile: 0, width: 1 },
  thinking: { smile: 0, width: 0.92 },
  speaking: { smile: 0, width: 1.05 },
  error: { smile: -0.08, width: 0.95 },
  happy: { smile: -0.24, width: 1.1 },
  concerned: { smile: 0.02, width: 0.95 },
  curious: { smile: -0.06, width: 0.98 },
  excited: { smile: -0.28, width: 1.18 },
  confused: { smile: 0.05, width: 0.9 },
  sleeping: { smile: 0.02, width: 0.85 },
}

export default function AgentMouth({ state, voice = true }: Props) {
  const upperLipRef = useRef<Mesh>(null)
  const lowerLipRef = useRef<Mesh>(null)
  const browLRef = useRef<Mesh>(null)
  const browRRef = useRef<Mesh>(null)

  const accent = AGENT3D_STYLES[state].accent
  const shape = MOUTH[state]

  useFrame(({ clock }) => {
    const anim = computeAgentAnimation(state, clock.elapsedTime)
    const talking = voice && (state === 'speaking' || state === 'recording' || state === 'excited')
    const v = talking ? getVoiceLevel() : 0
    const voiceOpen = v > 0.02 ? v : 0
    const sleeping = state === 'sleeping' ? 1 : 0
    const mouthOpen = Math.min(1, Math.max(anim.mouthOpen * 0.5, voiceOpen) * (1 - sleeping * 0.85))

    if (upperLipRef.current) upperLipRef.current.position.y = -mouthOpen * 0.1
    if (lowerLipRef.current) lowerLipRef.current.position.y = mouthOpen * 0.1
    if (browLRef.current) browLRef.current.rotation.z = -anim.brow
    if (browRRef.current) browRRef.current.rotation.z = anim.brow
  })

  return (
    <group position={[0, -0.45, 1.36]}>
      {/* Brow: left */}
      <mesh ref={browLRef} position={[-0.5, 0.78, 0]}>
        <boxGeometry args={[0.34, 0.045, 0.04]} />
        <meshStandardMaterial color={accent} emissive={accent} emissiveIntensity={1.4} />
      </mesh>
      {/* Brow: right */}
      <mesh ref={browRRef} position={[0.5, 0.78, 0]}>
        <boxGeometry args={[0.34, 0.045, 0.04]} />
        <meshStandardMaterial color={accent} emissive={accent} emissiveIntensity={1.4} />
      </mesh>

      {/* Upper lip */}
      <mesh ref={upperLipRef} position={[0, shape.smile, 0]}>
        <boxGeometry args={[0.5 * shape.width, 0.06, 0.04]} />
        <meshStandardMaterial color={accent} emissive={accent} emissiveIntensity={1.6} />
      </mesh>
      {/* Lower lip */}
      <mesh ref={lowerLipRef} position={[0, -0.1 + shape.smile, 0]}>
        <boxGeometry args={[0.44 * shape.width, 0.07, 0.04]} />
        <meshStandardMaterial color={accent} emissive={accent} emissiveIntensity={1.6} />
      </mesh>
    </group>
  )
}
