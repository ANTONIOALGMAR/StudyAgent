import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import type { Group, Mesh } from 'three'
import type { Agent3DState } from './agentStates'
import { AGENT3D_STYLES } from './agentStates'
import { computeAgentAnimation } from './animations/useAgentAnimation'
import AgentEyes from './AgentEyes'
import AgentMouth from './AgentMouth'

interface Props {
  state: Agent3DState
  voice?: boolean
}

export default function AgentHead({ state, voice = true }: Props) {
  const headRef = useRef<Group>(null)
  const shellRef = useRef<Mesh>(null)
  const ringRef = useRef<Mesh>(null)
  const accent = AGENT3D_STYLES[state].accent
  const body = AGENT3D_STYLES[state].color

  useFrame(({ mouse, clock }) => {
    const anim = computeAgentAnimation(state, clock.elapsedTime)
    if (headRef.current) {
      headRef.current.rotation.y = anim.headRotY + mouse.x * 0.12
      headRef.current.rotation.x = anim.headRotX - mouse.y * 0.08
      headRef.current.rotation.z = anim.lean + mouse.x * 0.04
    }
    if (ringRef.current) ringRef.current.rotation.z += 0.01
    if (shellRef.current) {
      shellRef.current.rotation.z = Math.sin(clock.elapsedTime * 1.4) * 0.02
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
        {/* Head shell */}
        <mesh ref={shellRef}>
          <sphereGeometry args={[1.5, 64, 64]} />
          <meshStandardMaterial color={body} metalness={0.7} roughness={0.25} />
        </mesh>

        {/* Holographic visor ring */}
        <mesh ref={ringRef} position={[0, 0, 1.42]}>
          <torusGeometry args={[1.35, 0.03, 16, 64]} />
          <meshStandardMaterial color={accent} emissive={accent} emissiveIntensity={1.8} />
        </mesh>

        <AgentEyes state={state} />
        <AgentMouth state={state} voice={voice} />

        {/* Antenna */}
        <mesh position={[0, 1.5, 0]}>
          <cylinderGeometry args={[0.03, 0.03, 0.3, 12]} />
          <meshStandardMaterial color={accent} emissive={accent} emissiveIntensity={1.5} />
        </mesh>
        <mesh position={[0, 1.72, 0]}>
          <icosahedronGeometry args={[0.09, 0]} />
          <meshStandardMaterial color={accent} emissive={accent} emissiveIntensity={2.4} />
        </mesh>
      </group>
    </group>
  )
}
