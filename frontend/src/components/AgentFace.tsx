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
}

const EYE_HEIGHT: Partial<Record<FaceState, number>> = {
  listening: 18,
  happy: 11,
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
  return <path d="M 42 66 Q 50 72 58 66" stroke={accent} strokeWidth="2.5" fill="none" strokeLinecap="round" />
}

export default function AgentFace({ state, size = 96 }: Props) {
  const c = COLORS[state]
  const eyeH = EYE_HEIGHT[state] ?? 16
  const waves = ['recording', 'speaking', 'thinking'].includes(state)
  return (
    <div className={`agent-face face-${state}`} style={{ width: size, height: size }}>
      <svg viewBox="0 0 100 100" width={size} height={size}>
        <g className="head">
          <circle cx="50" cy="52" r="40" fill="#161a23" stroke={c.accent} strokeWidth="2.5" />
          <circle cx="50" cy="52" r="46" fill="none" stroke={c.glow} strokeWidth="1.5" opacity="0.6" />

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

        {waves && (
          <g className="waves" stroke={c.accent} strokeWidth="1.6" fill="none" opacity="0.7">
            <path d="M 15 45 Q 10 52 15 59" />
            <path d="M 85 45 Q 90 52 85 59" />
          </g>
        )}
      </svg>
    </div>
  )
}
