import { Suspense, useEffect } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Float, Environment } from '@react-three/drei'
import AgentHead from './AgentHead'
import AgentParticles from './AgentParticles'
import type { Agent3DState } from './agentStates'
import { setVoiceSensitivity } from '../../lib/audioReactive'

interface Props {
  state: Agent3DState
  size?: number
  controls?: boolean
  voice?: boolean
  sensitivity?: number
  className?: string
}

export default function StudyAgentAvatar({
  state,
  size = 320,
  controls = false,
  voice = true,
  sensitivity = 3.2,
  className,
}: Props) {
  useEffect(() => {
    setVoiceSensitivity(sensitivity)
  }, [sensitivity])

  const divStyle = {
    width: size,
    height: size,
    background: 'radial-gradient(circle at 50% 42%, #0a1220 0%, #050b14 70%)',
    borderRadius: controls ? 24 : 14,
  }

  return (
    <div className={`studyagent-3d ${className ?? ''}`} style={divStyle}>
      <Canvas camera={{ position: [0, 0, 5], fov: 45 }} dpr={[1, 2]}>
        <Suspense fallback={null}>
          <ambientLight intensity={0.45} />
          <pointLight position={[5, 5, 5]} intensity={2} color="#5ba3f5" />
          <pointLight position={[-5, 2, 3]} intensity={1} color="#ffffff" />
          <pointLight position={[0, -3, 4]} intensity={0.8} color="#a78bfa" />

          <Float speed={1.4} rotationIntensity={0.25} floatIntensity={0.6}>
            <AgentHead state={state} voice={voice} />
          </Float>
          <AgentParticles state={state} />

          {controls && (
            <OrbitControls
              enableZoom={false}
              enablePan={false}
              minPolarAngle={Math.PI * 0.25}
              maxPolarAngle={Math.PI * 0.7}
              makeDefault
            />
          )}
          <Environment preset="city" />
        </Suspense>
      </Canvas>
    </div>
  )
}
