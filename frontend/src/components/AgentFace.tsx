export type FaceState = 'idle' | 'listening' | 'recording' | 'thinking' | 'speaking' | 'error'

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
}

export default function AgentFace({ state, size = 96 }: Props) {
  const c = COLORS[state]
  return (
    <div className={`agent-face face-${state}`} style={{ width: size, height: size }}>
      <svg viewBox="0 0 100 100" width={size} height={size}>
        <circle cx="50" cy="52" r="40" fill="#161a23" stroke={c.accent} strokeWidth="2.5" />
        <circle cx="50" cy="52" r="46" fill="none" stroke={c.glow} strokeWidth="1.5" opacity="0.6" />

        <line x1="50" y1="12" x2="50" y2="20" stroke={c.accent} strokeWidth="2.5" />
        <circle cx="50" cy="10" r="4" fill={c.accent} className="antenna-dot" />

        <g className="eyes">
          <g className="eye">
            <rect x="28" y="38" width="14" height={state === 'listening' ? 18 : 16} rx="7" fill={c.accent} />
            <circle cx="35" cy="47" r="3.2" fill="#0f1117" className="pupil pupil-left" />
          </g>
          <g className="eye">
            <rect x="58" y="38" width="14" height={state === 'listening' ? 18 : 16} rx="7" fill={c.accent} />
            <circle cx="65" cy="47" r="3.2" fill="#0f1117" className="pupil pupil-right" />
          </g>
          <g className="eyelids">
            <rect x="27" y="37" width="16" height="18" rx="8" fill="#161a23" className="lid lid-left" />
            <rect x="57" y="37" width="16" height="18" rx="8" fill="#161a23" className="lid lid-right" />
          </g>
        </g>

        {state === 'speaking' && (
          <ellipse cx="50" cy="68" rx="9" ry="6" fill={c.accent} className="mouth-speaking" />
        )}
        {state === 'listening' && (
          <ellipse cx="50" cy="68" rx="4.5" ry="5.5" fill={c.accent} />
        )}
        {(state === 'idle' || state === 'thinking') && (
          <path d="M 42 66 Q 50 72 58 66" stroke={c.accent} strokeWidth="2.5" fill="none" strokeLinecap="round" />
        )}
        {state === 'recording' && (
          <ellipse cx="50" cy="68" rx="7" ry="5" fill={c.accent} opacity="0.85" />
        )}
        {state === 'error' && (
          <path d="M 42 70 Q 50 63 58 70" stroke={c.accent} strokeWidth="2.5" fill="none" strokeLinecap="round" />
        )}

        {(state === 'recording' || state === 'speaking' || state === 'thinking') && (
          <g className="waves" stroke={c.accent} strokeWidth="1.6" fill="none" opacity="0.7">
            <path d="M 15 45 Q 10 52 15 59" />
            <path d="M 85 45 Q 90 52 85 59" />
          </g>
        )}
      </svg>
    </div>
  )
}
