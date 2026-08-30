import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import type { Group } from 'three'
import type { Agent3DState } from './agentStates'
import { computeAgentAnimation } from './animations/useAgentAnimation'
import AgentRealisticHead from './AgentRealisticHead'

interface Props {
  state: Agent3DState
  voice?: boolean
}

export default function AgentHead({ state, voice = true }: Props) {
  const headRef = useRef<Group>(null)

  useFrame(({ mouse, clock }) => {
    const anim = computeAgentAnimation(state, clock.elapsedTime)
    if (headRef.current) {
      headRef.current.rotation.y = anim.headRotY + mouse.x * 0.12
      headRef.current.rotation.x = anim.headRotX - mouse.y * 0.08
      headRef.current.rotation.z = anim.lean + mouse.x * 0.04
    }
  })

  return (
    <group>
      {/* Neck */}
      <mesh position={[0, -1.6, 0]}>
        <cylinderGeometry args={[0.35, 0.45, 0.6, 24]} />
        <meshStandardMaterial color="#11151f" metalness={0.8} roughness={0.4} />
      </mesh>

      <group ref={headRef} position={[0, 0.2, 0]}>
        <AgentRealisticHead state={state} voice={voice} />
      </group>
    </group>
  )
}
