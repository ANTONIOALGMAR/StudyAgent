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

// ── Tutor: Flashcards ──────────────────────────────────────────────────────────

export interface FlashcardDeck {
  id: string
  title: string
  topic: string
  source_doc: string | null
  card_count: number
  created_at: string
}

export interface Flashcard {
  id: string
  deck_id: string
  front: string
  back: string
  easiness: number
  interval_days: number
  repetitions: number
  next_review: string
}

export interface FlashcardReviewResult {
  card_id: string
  difficulty: string
  easiness: number
  interval_days: number
  next_review: string
}

export async function getFlashcardDecks(): Promise<FlashcardDeck[]> {
  const res = await fetch(`${API}/api/flashcards/decks`)
  if (!res.ok) throw new Error('Falha ao listar baralhos')
  return res.json()
}

export async function flashcardDeckStats(deckId: string) {
  const res = await fetch(`${API}/api/flashcards/decks/${deckId}/stats`)
  if (!res.ok) throw new Error('Falha ao carregar stats')
  return res.json()
}

export async function generateFlashcards(
  topic: string,
  n = 10,
  level = 'ensino fundamental',
): Promise<{ deck_id: string; card_count: number }> {
  const res = await fetch(`${API}/api/flashcards/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, n, level }),
  })
  if (!res.ok) throw new Error((await res.json()).detail || 'Falha ao gerar flashcards')
  return res.json()
}

export async function getDueCards(deckId: string): Promise<Flashcard[]> {
  const res = await fetch(`${API}/api/flashcards/decks/${deckId}/due`)
  if (!res.ok) throw new Error('Falha ao buscar cards')
  return res.json()
}

export async function reviewFlashcard(
  cardId: string,
  difficulty: string,
): Promise<FlashcardReviewResult> {
  const res = await fetch(`${API}/api/flashcards/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ card_id: cardId, difficulty }),
  })
  if (!res.ok) throw new Error((await res.json()).detail || 'Falha ao registrar review')
  return res.json()
}

// ── Tutor: Study Plans ─────────────────────────────────────────────────────────

export interface StudyPlan {
  id: string
  title: string
  topic: string
  total_items: number
  done_items: number
  created_at: string
  items?: StudyItem[]
}

export interface StudyItem {
  id: number
  plan_id: string
  title: string
  detail: string
  done: number
  sort_order: number
}

export async function getStudyPlans(): Promise<StudyPlan[]> {
  const res = await fetch(`${API}/api/study-plans`)
  if (!res.ok) throw new Error('Falha ao listar planos')
  return res.json()
}

export async function generateStudyPlan(
  topic: string,
  level = 'ensino fundamental',
): Promise<StudyPlan> {
  const res = await fetch(`${API}/api/study-plans/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, level }),
  })
  if (!res.ok) throw new Error((await res.json()).detail || 'Falha ao gerar plano')
  return res.json()
}

export async function getStudyPlan(planId: string): Promise<StudyPlan> {
  const res = await fetch(`${API}/api/study-plans/${planId}`)
  if (!res.ok) throw new Error('Falha ao carregar plano')
  return res.json()
}

export async function toggleStudyItem(itemId: number) {
  const res = await fetch(`${API}/api/study-plans/items/${itemId}/toggle`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error('Falha ao atualizar item')
  return res.json()
}

// ── Tutor: Stats ───────────────────────────────────────────────────────────────

export interface Dashboard {
  exercises: {
    total_sessions: number
    avg_percent: number
    total_correct: number
    total_questions: number
    streak_days: number
    recent: { topic: string; score: number; total: number; percent: number; created_at: string }[]
  }
  flashcards: {
    total_decks: number
    total_cards: number
    due_now: number
    mastered: number
    reviews_last_7d: number
  }
  study_plans: {
    total_plans: number
    total_items: number
    done_items: number
    overall_percent: number
    plans: { id: string; title: string; total_items: number; done_items: number; percent: number }[]
  }
}

export async function getDashboard(): Promise<Dashboard> {
  const res = await fetch(`${API}/api/stats/dashboard`)
  if (!res.ok) throw new Error('Falha ao carregar dashboard')
  return res.json()
}

// ── P6: Profile ────────────────────────────────────────────────────────────────

export interface Profile {
  name: string
  grade: string
  school: string
  preferences: string
}

export interface TopicMastery {
  topic: string
  attempts: number
  correct: number
  total_questions: number
  avg_percent: number
  last_practiced: string | null
}

export interface ProfileInsights {
  profile: Profile | null
  weak_topics: { topic: string; avg_percent: number; attempts: number }[]
  strong_topics: { topic: string; avg_percent: number; attempts: number }[]
  suggestions: { topic: string; avg_percent: number }[]
  total_topics_studied: number
}

export async function getProfile(): Promise<Profile> {
  const res = await fetch(`${API}/api/profile`)
  if (!res.ok) throw new Error('Falha ao carregar perfil')
  return res.json()
}

export async function saveProfile(
  name: string, grade: string, school: string, preferences: string,
): Promise<Profile> {
  const res = await fetch(`${API}/api/profile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, grade, school, preferences }),
  })
  if (!res.ok) throw new Error('Falha ao salvar perfil')
  return res.json()
}

export async function getProfileInsights(): Promise<ProfileInsights> {
  const res = await fetch(`${API}/api/profile/insights`)
  if (!res.ok) throw new Error('Falha ao carregar insights')
  return res.json()
}

export async function getMastery(): Promise<TopicMastery[]> {
  const res = await fetch(`${API}/api/mastery`)
  if (!res.ok) throw new Error('Falha ao carregar mastery')
  return res.json()
}

// ── P7: Action Proposals ──────────────────────────────────────────────────────

export interface ActionProposal {
  id: string
  action_type: string
  label: string
  description: string
  params: Record<string, unknown>
  status: string
}

export async function getPendingActions(): Promise<ActionProposal[]> {
  const res = await fetch(`${API}/api/actions/pending`)
  if (!res.ok) throw new Error('Falha ao buscar ações pendentes')
  return res.json()
}

export async function approveAction(proposalId: string) {
  const res = await fetch(`${API}/api/actions/${proposalId}/approve`, { method: 'POST' })
  if (!res.ok) throw new Error('Falha ao aprovar ação')
  return res.json()
}

export async function rejectAction(proposalId: string) {
  const res = await fetch(`${API}/api/actions/${proposalId}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason: 'Recusado pelo aluno' }),
  })
  if (!res.ok) throw new Error('Falha ao rejeitar ação')
  return res.json()
}
