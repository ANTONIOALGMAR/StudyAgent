const API = 'http://localhost:8000'

export interface ChatResponse {
  session_id: string
  response: string
  tools_used: string[]
}

export async function chat(message: string, sessionId: string | null, useScreen: boolean): Promise<ChatResponse> {
  const res = await fetch(`${API}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId, use_screen: useScreen }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? `Erro ${res.status}`)
  }
  return res.json()
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
