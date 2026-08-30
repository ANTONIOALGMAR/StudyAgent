import { useEffect, useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { useGLTF } from '@react-three/drei'
import * as THREE from 'three'
import type { Group, Mesh } from 'three'
import type { Agent3DState } from './agentStates'
import { AGENT3D_STYLES } from './agentStates'
import { computeAgentAnimation } from './animations/useAgentAnimation'
import { getVoiceLevel } from '../../lib/audioReactive'
import { createIrisTexture, createScleraTexture } from './eyeTextures'

interface Props {
  state: Agent3DState
  voice?: boolean
}

const TARGET_HEAD_HEIGHT = 2.9
const HEAD_CENTER_Y = 0.0

// Ordem dos 26 morph targets do vitruvian_head.glb (mesh.extras.targetNames)
const MORPH_NAMES = [
  'Jaw_Lower',
  'Mouth_Large_Opened',
  'Lips_Up_Funnel',
  'Lips_Up_Corner_Wide_Left',
  'Lips_Up_Corner_Wide_Right',
  'Happy',
  'Sad',
  'Angry',
  'Scared',
  'Disgusted',
  'Thinking',
  'Kiss',
  'Smile_Lips_Closed',
  'Eyebrows_Raised_Left',
  'Eyebrows_Raised_Right',
  'Eyebrows_Frown_Left',
  'Eyebrows_Frown_Right',
  'Eyes_Closed_Max',
  'Eyes_Opened_Max_Left',
  'Eyes_Opened_Max_Right',
  'Eyes_Squint',
  'aa_02',
  'ow_08',
  'p_b_m_21',
  'f_v_18',
  'ey_eh_uh_04',
]

const clamp = (v: number, min: number, max: number) => Math.min(max, Math.max(min, v))

function morphIndex(
  mesh: Mesh,
  name: string,
  fallback: (n: string) => number | undefined,
): number {
  const dict = (mesh as Mesh & { morphTargetDictionary?: Record<string, number> }).morphTargetDictionary
  const byName = dict ? dict[name] : undefined
  if (byName !== undefined) return byName
  const fb = fallback(name)
  return fb !== undefined ? fb : -1
}

export default function AgentRealisticHead({ state, voice = true }: Props) {
  const groupRef = useRef<Group>(null)
  const morphRef = useRef<Mesh | null>(null)
  const morphListRef = useRef<Mesh[]>([])

  const { scene } = useGLTF('/models/vitruvian_head.glb') as any

  const accent = AGENT3D_STYLES[state].accent

  const material = useMemo(() => {
    const m = new THREE.MeshStandardMaterial({
      color: new THREE.Color('#ffffff'),
      emissive: new THREE.Color('#2f7bff'),
      emissiveIntensity: 0.45,
      metalness: 0.0,
      roughness: 0.5,
      transparent: true,
      opacity: 1.0,
      depthWrite: true,
      vertexColors: true,
      side: THREE.DoubleSide,
      toneMapped: false,
    })
    ;(m as unknown as { morphTargets: boolean }).morphTargets = true
    return m
  }, [])

  // Olhos naturais: geometria do asset preservada, mas com texturas
  // procedurais (íris azul com pupila/limbo/raios, sclera branca com veias)
  // e córnea vítrea brilhante. O emissivo azul fica só na pele.
  const eyeMaterials = useMemo(() => {
    const irisTex = createIrisTexture('azul')
    const scleraTex = createScleraTexture()
    const base = (opts: Partial<THREE.MeshStandardMaterialParameters>) =>
      new THREE.MeshStandardMaterial({
        side: THREE.DoubleSide,
        toneMapped: false,
        roughness: 0.3,
        metalness: 0,
        ...opts,
      })
    return {
      sclera: base({ map: scleraTex, roughness: 0.25 }),
      iris: base({ map: irisTex, roughness: 0.08 }),
      cornea: base({
        color: '#ffffff',
        transparent: true,
        opacity: 0.12,
        roughness: 0.04,
        metalness: 0.05,
        depthWrite: false,
      }),
      eyeBack: base({ color: '#0c0c0c', roughness: 0.7 }),
      detail: base({ color: '#ffffff', roughness: 0.5 }),
    }
  }, [])

  useEffect(() => {
    if (!scene) return
    scene.traverse((obj: THREE.Object3D) => {
      if ((obj as Mesh).isMesh) {
        const mesh = obj as Mesh
        const parentName = (mesh.parent?.name || '').toLowerCase()
        // Olhos: meshes dentro dos nós Eye_L_eyeball / Eye_R_eyeball,
        // distinguidos pelo sufixo (sclera, iris _1, eyeBack _2, cornea _3).
        if (parentName === 'eye_l_eyeball' || parentName === 'eye_r_eyeball') {
          const sfx = (mesh.name.match(/_(\d+)$/) || [])[1]
          if (sfx === '1') mesh.material = eyeMaterials.iris
          else if (sfx === '2') mesh.material = eyeMaterials.eyeBack
          else if (sfx === '3') mesh.material = eyeMaterials.cornea
          else mesh.material = eyeMaterials.sclera
        } else {
          mesh.material = material
        }
        if (mesh.morphTargetInfluences && mesh.morphTargetInfluences.length) {
          mesh.morphTargetInfluences.fill(0)
          morphListRef.current.push(mesh)
          if (!morphRef.current) morphRef.current = mesh
        }
      }
    })
  }, [scene, material, eyeMaterials])

  useFrame(({ clock, mouse }) => {
    const group = groupRef.current
    if (!group || !scene) return

    if (!group.userData.__scaled) {
      const box = new THREE.Box3().setFromObject(group)
      const size = box.getSize(new THREE.Vector3())
      const center = box.getCenter(new THREE.Vector3())
      const s = TARGET_HEAD_HEIGHT / Math.max(size.y, 0.0001)
      group.scale.setScalar(s)
      group.position.set(
        -center.x * s,
        HEAD_CENTER_Y - center.y * s,
        -center.z * s,
      )
      group.userData.__scaled = true
    }

    const mesh = morphRef.current
    if (!mesh) return
    const anim = computeAgentAnimation(state, clock.elapsedTime)
    const idxOf = (n: string) => morphIndex(mesh, n, (nn) => MORPH_NAMES.indexOf(nn))
    const inf = mesh.morphTargetInfluences ?? []
    inf.fill(0)

    const set = (name: string, v: number) => {
      const i = idxOf(name)
      if (i >= 0) inf[i] = clamp(v, 0, 1)
    }

    const talking =
      voice &&
      (state === 'speaking' || state === 'recording' || state === 'excited' || state === 'happy')
    const v = talking ? getVoiceLevel() : 0
    const voiceOpen = v > 0.02 ? v : 0
    const sleeping = state === 'sleeping'

    // --- Boca (definida, discretamente aberta — nunca escancarada) ---
    // Limita a abertura máxima (~50%) e suaviza a curva para a boca não
    // parecer gritando ao falar.
    const open = clamp((anim.mouthOpen * 0.55 + voiceOpen * 0.5) * 1.0, 0, 1)
    const capped = clamp(open * 0.5, 0, 0.5)
    set('Jaw_Lower', capped)
    set('Mouth_Large_Opened', clamp(capped * capped * 0.7 + capped * 0.2, 0, 0.5))
    set('Lips_Up_Funnel', clamp(capped * 0.35, 0, 1))

    // Visemes simulando fala (duas fases rítmicas)
    const ph = (clock.elapsedTime * 7) % 1
    const openFrac = Math.abs(ph - 0.5) * 2
    const speech = voiceOpen
    if (talking) {
      set('aa_02', speech * (1 - openFrac) * 0.5)
      set('ow_08', speech * openFrac * 0.35)
      set('p_b_m_21', speech * (openFrac > 0.75 ? 1 : 0) * 0.3)
      set('Kiss', speech * (openFrac < 0.25 ? 0.15 : 0))
    }

    // --- Sorriso / expressões ---
    let smile = 0
    if (state === 'happy' || state === 'excited') smile = 0.55
    else if (state === 'curious') smile = 0.2
    else if (state === 'idle' || state === 'listening' || state === 'recording') smile = 0.08
    if (smile > 0) {
      set('Happy', smile)
      set('Smile_Lips_Closed', smile * 0.5)
      set('Lips_Up_Corner_Wide_Left', smile * 0.5)
      set('Lips_Up_Corner_Wide_Right', smile * 0.5)
    }
    if (state === 'error' || state === 'confused' || state === 'concerned') {
      set('Sad', 0.4)
    }
    if (state === 'error') set('Angry', 0.4)
    if (state === 'thinking' || state === 'confused') set('Thinking', 0.5)
    if (state === 'curious') set('Thinking', 0.2)

    // --- Sobrancelhas (brow: + = levantada/franzida conforme estado) ---
    const browRaise =
      state === 'curious' || state === 'excited' || state === 'thinking' ? clamp(anim.brow, 0, 1) : 0
    const browFrown =
      state === 'concerned' || state === 'confused' || state === 'error'
        ? clamp(anim.brow < 0 ? -anim.brow : anim.brow, 0, 1)
        : 0
    set('Eyebrows_Raised_Left', browRaise * 0.8)
    set('Eyebrows_Raised_Right', browRaise * 0.8)
    set('Eyebrows_Frown_Left', browFrown * 0.8)
    set('Eyebrows_Frown_Right', browFrown * 0.8)

    // --- Olhos ---
    const squintState =
      state === 'thinking' || state === 'confused' || state === 'concerned' || state === 'curious'
    if (sleeping || anim.blink) set('Eyes_Closed_Max', 1)
    else {
      set('Eyes_Squint', squintState ? 0.55 : 0)
      if (state === 'excited' || state === 'curious') {
        set('Eyes_Opened_Max_Left', 0.5)
        set('Eyes_Opened_Max_Right', 0.5)
      }
    }

    // Micro-movimento do olhar (dirige um leve desvio — aqui via rotação dos olhos)
    const t = clock.elapsedTime
    // Micro-sacadas: pequenos desvios rápidos e erráticos que dão "vida" ao olhar
    const saccade = sleeping
      ? 0
      : 0.22 * Math.sin(t * 7.3) * Math.sin(t * 3.1) + 0.15 * Math.sin(t * 11.7 + 1.3)
    const lookX = clamp(anim.lookX * 0.6 + mouse.x * 0.35 + saccade, -1, 1)
    const lookY = clamp(anim.lookY * 0.5 + mouse.y * 0.25 + saccade * 0.4, -1, 1)
    group.traverse((obj) => {
      if (obj.name === 'Eye_L_eyeball' || obj.name === 'Eye_R_eyeball') {
        obj.rotation.set(0, 0, 0)
        obj.rotateY(lookX * 0.55)
        obj.rotateX(lookY * 0.34)
      }
    })

    for (const mm of morphListRef.current) {
      if (mm === mesh) continue
      const mInf = mm.morphTargetInfluences
      if (!mInf) continue
      for (let i = 0; i < inf.length; i++) mInf[i] = inf[i]
    }

    material.emissive.set(accent)
    material.emissiveIntensity = 0.42 + 0.15 * Math.sin(clock.elapsedTime * 2.0)
  })

  return (
    <group ref={groupRef} position={[0, HEAD_CENTER_Y, 0]}>
      <primitive object={scene} />
    </group>
  )
}
