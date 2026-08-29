import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import type { Group, Mesh } from 'three'
import type { Agent3DState } from './agentStates'
import { AGENT3D_STYLES } from './agentStates'
import { computeAgentAnimation } from './animations/useAgentAnimation'

interface Props {
  state: Agent3DState
}

const clamp = (v: number, min: number, max: number) => Math.min(max, Math.max(min, v))

export default function AgentEyes({ state }: Props) {
  const lidLRef = useRef<Mesh>(null)
  const lidRRef = useRef<Mesh>(null)
  const groupRef = useRef<Group>(null)

  const accent = AGENT3D_STYLES[state].eye

  useFrame(({ mouse, clock }) => {
    const anim = computeAgentAnimation(state, clock.elapsedTime)
    const tx = clamp(anim.lookX + mouse.x * 0.25, -0.3, 0.3)
    const ty = clamp(anim.lookY + mouse.y * 0.2, -0.25, 0.3)
    if (groupRef.current) {
      groupRef.current.position.x = tx * 0.55
      groupRef.current.position.y = ty * 0.55
    }
    const open = anim.blink ? 0.06 : 0.24
    if (lidLRef.current) lidLRef.current.scale.y = open
    if (lidRRef.current) lidRRef.current.scale.y = open
  })

  return (
    <group ref={groupRef}>
      <mesh position={[-0.55, 0.22, 1.32]}>
        <sphereGeometry args={[0.22, 32, 32]} />
        <meshStandardMaterial color={accent} emissive={accent} emissiveIntensity={2} />
      </mesh>
      <mesh position={[0.55, 0.22, 1.32]}>
        <sphereGeometry args={[0.22, 32, 32]} />
        <meshStandardMaterial color={accent} emissive={accent} emissiveIntensity={2} />
      </mesh>

      {/* Eyelids (blink) */}
      <mesh ref={lidLRef} position={[-0.55, 0.42, 1.36]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.26, 0.26, 0.02, 32]} />
        <meshStandardMaterial color="#0b0d13" />
      </mesh>
      <mesh ref={lidRRef} position={[0.55, 0.42, 1.36]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.26, 0.26, 0.02, 32]} />
        <meshStandardMaterial color="#0b0d13" />
      </mesh>
    </group>
  )
}
