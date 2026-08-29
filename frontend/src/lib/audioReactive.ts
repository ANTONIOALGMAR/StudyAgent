let analyser: AnalyserNode | null = null
const buf = new Float32Array(2048)

let smLevel = 0
const ATTACK = 0.35
const RELEASE = 0.08

let voiceGain = 3.2

export function setVoiceSensitivity(gain: number): void {
  voiceGain = Math.max(0.5, Math.min(8, gain))
}

export function getVoiceSensitivity(): number {
  return voiceGain
}

export function registerVoiceAnalyser(node: AnalyserNode | null): void {
  analyser = node
  if (node) node.fftSize = 2048
  if (!node) smLevel = 0
}

export function getVoiceLevel(): number {
  if (!analyser) { smLevel = 0; return 0 }
  analyser.getFloatTimeDomainData(buf)
  let sum = 0
  for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i]
  const rms = Math.sqrt(sum / buf.length) * voiceGain
  const raw = Math.min(1, rms)
  smLevel = raw > smLevel
    ? smLevel + (raw - smLevel) * ATTACK
    : smLevel + (raw - smLevel) * RELEASE
  return smLevel
}
