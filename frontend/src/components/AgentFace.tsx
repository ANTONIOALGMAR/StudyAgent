export type FaceState =
  | 'idle'
  | 'listening'
  | 'recording'
  | 'thinking'
  | 'speaking'
  | 'error'
  | 'happy'
  | 'concerned'
  | 'curious'
  | 'excited'
  | 'confused'
  | 'sleeping'

interface Props {
  state: FaceState
  size?: number
}

const COLORS: Record<FaceState, { glow: string; accent: string }> = {
  idle: { glow: '#262b38', accent: '#8b93a7' },
  listening: { glow: '#12321f', accent: '#34d27b' },
  recording: { glow: '#3b1220', accent: '#f87171' },
  thinking: { glow: '#12253b', accent: '#5ba3f5' },
  speaking: { glow: '#251a3d', accent: '#a78bfa' },
  error: { glow: '#3b1220', accent: '#f87171' },
  happy: { glow: '#12321f', accent: '#34d27b' },
  concerned: { glow: '#3d2f12', accent: '#fbbf24' },
  curious: { glow: '#12253b', accent: '#5ba3f5' },
  excited: { glow: '#3b1230', accent: '#f472b6' },
  confused: { glow: '#3d2f12', accent: '#fb923c' },
  sleeping: { glow: '#1b2030', accent: '#94a3b8' },
}

const EYE_HEIGHT: Partial<Record<FaceState, number>> = {
  listening: 18,
  happy: 11,
  excited: 20,
  sleeping: 4,
}

function Mouth({ state, accent }: { state: FaceState; accent: string }) {
  if (state === 'speaking')
    return <ellipse cx="50" cy="68" rx="9" ry="6" fill={accent} className="mouth-speaking" />
  if (state === 'listening')
    return <ellipse cx="50" cy="68" rx="4.5" ry="5.5" fill={accent} />
  if (state === 'recording')
    return <ellipse cx="50" cy="68" rx="7" ry="5" fill={accent} opacity="0.85" />
  if (state === 'happy')
    return (
      <path
        d="M 39 63 Q 50 75 61 63"
        stroke={accent}
        strokeWidth="2.8"
        fill="none"
        strokeLinecap="round"
      />
    )
  if (state === 'error')
    return <path d="M 42 70 Q 50 63 58 70" stroke={accent} strokeWidth="2.5" fill="none" strokeLinecap="round" />
  if (state === 'concerned')
    return <path d="M 43 68 L 57 68" stroke={accent} strokeWidth="2.5" fill="none" strokeLinecap="round" />
  if (state === 'curious')
    return <path d="M 44 67 Q 52 72 59 65" stroke={accent} strokeWidth="2.5" fill="none" strokeLinecap="round" />
  if (state === 'excited')
    return <ellipse cx="50" cy="69" rx="8" ry="9" fill={accent} className="mouth-speaking" />
  if (state === 'confused')
    return <path d="M 43 68 Q 46 71 50 67 Q 54 63 57 68" stroke={accent} strokeWidth="2.5" fill="none" strokeLinecap="round" />
  if (state === 'sleeping')
    return <path d="M 45 68 Q 50 70 55 68" stroke={accent} strokeWidth="2.2" fill="none" strokeLinecap="round" />
  return <path d="M 42 66 Q 50 72 58 66" stroke={accent} strokeWidth="2.5" fill="none" strokeLinecap="round" />
}

export default function AgentFace({ state, size = 96 }: Props) {
  const c = COLORS[state]
  const eyeH = EYE_HEIGHT[state] ?? 16
  const waves = ['recording', 'speaking', 'thinking'].includes(state)
  return (
    <div className={`agent-face face-${state}`} style={{ width: size, height: size }}>
      <div className="face-3d-wrap">
        {/* Anéis holográficos externos (projeção 3D) */}
        <div className="hologram-ring ring-1" style={{ borderColor: c.accent }} />
        <div className="hologram-ring ring-2" style={{ background: `radial-gradient(circle, ${c.glow}55 0%, transparent 70%)` }} />

        <svg viewBox="0 0 100 100" width={size} height={size} className="face-core">
          <defs>
            <radialGradient id={`faceShade-${state}`} cx="50%" cy="38%" r="75%">
              <stop offset="0%" stopColor="#2a3140" />
              <stop offset="70%" stopColor="#161a23" />
              <stop offset="100%" stopColor="#0b0d13" />
            </radialGradient>
            <linearGradient id={`visor-${state}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#ffffff" stopOpacity="0.35" />
              <stop offset="40%" stopColor="#ffffff" stopOpacity="0.06" />
              <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
            </linearGradient>
            <filter id={`neon-${state}`} x="-60%" y="-60%" width="220%" height="220%">
              <feGaussianBlur stdDeviation="1.6" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Dome holográfico */}
          <ellipse cx="50" cy="50" rx="47" ry="53" fill="none" stroke={c.accent} strokeWidth="0.6" opacity="0.35" strokeDasharray="2 3" className="hologram-dome" />

          {/* Cabeça 3D: gradiente + sombra profunda + brilho de visor */}
          <g className="head">
            <circle cx="50" cy="52" r="40" fill={`url(#faceShade-${state})`} stroke={c.accent} strokeWidth="2.5" filter={`url(#neon-${state})`} />
            <circle cx="50" cy="52" r="38.5" fill="none" stroke={`url(#visor-${state})`} strokeWidth="3" />
            <ellipse cx="34" cy="30" rx="13" ry="7" fill="#ffffff" opacity="0.14" className="specular" />

            <line x1="50" y1="12" x2="50" y2="20" stroke={c.accent} strokeWidth="2.5" />
            <circle cx="50" cy="10" r="4" fill={c.accent} className="antenna-dot" />

            <g className="brows">
              <path className="brow brow-left" d="M 27 33 Q 35 28 43 32" stroke={c.accent} strokeWidth="2.4" fill="none" strokeLinecap="round" />
              <path className="brow brow-right" d="M 57 32 Q 65 28 73 33" stroke={c.accent} strokeWidth="2.4" fill="none" strokeLinecap="round" />
            </g>

            <g className="eyes">
              <g className="eye">
                <rect x="28" y="38" width="14" height={eyeH} rx="7" fill={c.accent} />
                <circle cx="35" cy={38 + eyeH / 2 + 1} r="3.2" fill="#0f1117" className="pupil pupil-left" />
              </g>
              <g className="eye">
                <rect x="58" y="38" width="14" height={eyeH} rx="7" fill={c.accent} />
                <circle cx="65" cy={38 + eyeH / 2 + 1} r="3.2" fill="#0f1117" className="pupil pupil-right" />
              </g>
              <g className="eyelids">
                <rect x="27" y="37" width="16" height="18" rx="8" fill="#161a23" className="lid lid-left" />
                <rect x="57" y="37" width="16" height="18" rx="8" fill="#161a23" className="lid lid-right" />
              </g>
            </g>

            <g className="cheeks">
              <circle cx="24" cy="61" r="5.5" fill="#f472b6" className="cheek cheek-left" />
              <circle cx="76" cy="61" r="5.5" fill="#f472b6" className="cheek cheek-right" />
            </g>

            <Mouth state={state} accent={c.accent} />
          </g>

          {/* Partículas futuristas */}
          <g className="particles" fill={c.accent}>
            <circle cx="16" cy="26" r="1.4" className="particle p1" />
            <circle cx="84" cy="22" r="1.1" className="particle p2" />
            <circle cx="12" cy="58" r="1" className="particle p3" />
            <circle cx="88" cy="64" r="1.3" className="particle p4" />
            <circle cx="20" cy="82" r="1.1" className="particle p5" />
            <circle cx="80" cy="86" r="1.2" className="particle p6" />
          </g>

          {/* Linha de varredura holográfica */}
          {waves && (
            <g className="waves" stroke={c.accent} strokeWidth="1.6" fill="none" opacity="0.7">
              <path d="M 15 45 Q 10 52 15 59" />
              <path d="M 85 45 Q 90 52 85 59" />
            </g>
          )}
        </svg>

        {/* Grade holográfica em camada (CSS) */}
        <div className="holo-grid" style={{ borderColor: c.accent, boxShadow: `0 0 ${size * 0.14}px ${c.glow}` }} />
        <div className="scanline" style={{ background: `linear-gradient(180deg, transparent, ${c.accent}66, transparent)` }} />
      </div>
    </div>
  )
}
