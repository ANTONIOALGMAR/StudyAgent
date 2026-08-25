const API = 'http://localhost:8000'

export interface ChatResponse {
  session_id: string
  response: string
  tools_used: string[]
}

export async function chat(
  message: string,
  sessionId: string | null,
  useScreen: boolean,
  imageB64?: string | null,
  monitor: number = 1,
  docId?: string | null,
): Promise<ChatResponse> {
  const res = await fetch(`${API}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      use_screen: useScreen,
      image_b64: imageB64 ?? null,
      monitor,
      doc_id: docId ?? null,
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? `Erro ${res.status}`)
  }
  return res.json()
}

export interface UploadedDoc {
  id: string
  name: string
  pages: number
  chars: number
}

export async function uploadDocument(file: File): Promise<UploadedDoc> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API}/api/documents/upload`, { method: 'POST', body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? `Erro ${res.status}`)
  }
  return res.json()
}

export interface DocAudioPlan {
  total: number
  kind: 'página' | 'parte'
  name: string
}

export async function getDocAudioPlan(docId: string): Promise<DocAudioPlan> {
  const res = await fetch(`${API}/api/documents/${docId}/audio/plan`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? `Erro ${res.status}`)
  }
  return res.json()
}

export function documentAudioUrl(docId: string, idx: number): string {
  return `${API}/api/documents/${docId}/audio?idx=${idx}`
}

export interface PermissionMap {
  [key: string]: boolean
}

export async function getPermissions(): Promise<PermissionMap> {
  const res = await fetch(`${API}/api/permissions`)
  return res.json()
}

export async function setPermission(name: string, value: boolean): Promise<void> {
  await fetch(`${API}/api/permissions/${name}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ value }),
  })
}

export async function captureScreen(): Promise<{ image_b64: string; text: string }> {
  const res = await fetch(`${API}/api/screen/capture`, { method: 'POST' })
  if (!res.ok) throw new Error('Falha ao capturar tela')
  return res.json()
}

export async function transcribeAudio(blob: Blob): Promise<string> {
  const form = new FormData()
  form.append('file', blob, 'gravacao.webm')
  const res = await fetch(`${API}/api/audio/transcribe`, { method: 'POST', body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? `Erro ${res.status}`)
  }
  const data = await res.json()
  return data.text as string
}

export async function speak(text: string): Promise<Blob> {
  const res = await fetch(`${API}/api/audio/speak`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
  if (!res.ok) throw new Error('Falha ao sintetizar voz')
  return res.blob()
}

export const PERMISSION_LABELS: Record<string, string> = {
  microphone: 'Microfone',
  camera: 'Câmera',
  screen_capture: 'Captura de tela',
  file_access: 'Acesso a arquivos',
  internet: 'Internet',
  mouse_control: 'Controle do mouse',
  keyboard_control: 'Controle do teclado',
  command_execution: 'Executar comandos',
}

export interface MonitorInfo {
  index: number
  width: number
  height: number
  left: number
  top: number
}

export async function getMonitors(): Promise<MonitorInfo[]> {
  const res = await fetch(`${API}/api/screen/monitors`)
  if (!res.ok) return []
  const data = await res.json()
  return data.monitors as MonitorInfo[]
}

export function screenPreviewUrl(monitor: number): string {
  return `${API}/api/screen/preview?monitor=${monitor}`
}

export interface ExerciseQuestion {
  id: string
  q: string
  options: string[] | null
}

export interface ExerciseSet {
  exercise_id: string
  topic: string
  questions: ExerciseQuestion[]
}

export interface ExerciseResultItem {
  id: string
  q: string
  user_answer: string
  expected: string
  correct: boolean
  explanation: string
}

export interface GradeResult {
  exercise_id: string
  score: number
  total: number
  percent: number
  message: string
  results: ExerciseResultItem[]
}

export async function generateExercises(
  topic: string,
  n = 4,
  level = 'ensino fundamental',
): Promise<ExerciseSet> {
  const res = await fetch(`${API}/api/exercises/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, n, level }),
  })
  if (!res.ok) throw new Error((await res.json()).detail || 'Falha ao gerar exercícios')
  return res.json()
}

export async function gradeExercise(
  exerciseId: string,
  answers: Record<string, string>,
): Promise<GradeResult> {
  const res = await fetch(`${API}/api/exercises/grade`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ exercise_id: exerciseId, answers }),
  })
  if (!res.ok) throw new Error((await res.json()).detail || 'Falha ao corrigir')
  return res.json()
}

export function documentFileUrl(id: string): string {
  return `${API}/api/documents/${id}/file`
}
