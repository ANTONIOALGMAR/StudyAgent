export type Agent3DState =
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

export interface AgentStyle {
  color: string
  accent: string
  accentIntensity: number
  eye: string
}

export const AGENT3D_STYLES: Record<Agent3DState, AgentStyle> = {
  idle: { color: '#d9e1e8', accent: '#5ba3f5', accentIntensity: 1.2, eye: '#5ba3f5' },
  listening: { color: '#d9e1e8', accent: '#34d27b', accentIntensity: 1.8, eye: '#34d27b' },
  recording: { color: '#e8d9d9', accent: '#f87171', accentIntensity: 2, eye: '#f87171' },
  thinking: { color: '#d9e1e8', accent: '#5ba3f5', accentIntensity: 1.6, eye: '#7cc4ff' },
  speaking: { color: '#e6ddf0', accent: '#a78bfa', accentIntensity: 1.8, eye: '#a78bfa' },
  error: { color: '#e8d9d9', accent: '#f87171', accentIntensity: 2, eye: '#f87171' },
  happy: { color: '#ddead9', accent: '#34d27b', accentIntensity: 1.8, eye: '#34d27b' },
  concerned: { color: '#e8e2d9', accent: '#fbbf24', accentIntensity: 1.5, eye: '#fbbf24' },
  curious: { color: '#d9e1e8', accent: '#5ba3f5', accentIntensity: 1.5, eye: '#7cc4ff' },
  excited: { color: '#f0dde8', accent: '#f472b6', accentIntensity: 2.2, eye: '#f472b6' },
  confused: { color: '#e8e2d9', accent: '#fbbf24', accentIntensity: 1.6, eye: '#fb923c' },
  sleeping: { color: '#cdd4e0', accent: '#64748b', accentIntensity: 0.9, eye: '#94a3b8' },
}

export const AGENT3D_LABELS: Record<Agent3DState, string> = {
  idle: 'pronto para ajudar',
  listening: 'ouvindo você…',
  recording: 'gravando sua voz',
  thinking: 'pensando…',
  speaking: 'falando',
  error: 'ops, algo deu errado',
  happy: 'ficou feliz com você! 🎉',
  concerned: 'quer te ajudar a melhorar',
  curious: 'fez uma pergunta pra você',
  excited: 'mal posso esperar! ⚡',
  confused: 'deixa eu pensar melhor…',
  sleeping: 'em repouso 😴',
}
