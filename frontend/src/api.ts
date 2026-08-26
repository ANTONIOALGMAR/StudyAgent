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

export interface EnhancedDashboard extends Dashboard {
  mastery_by_subject: {
    subject: string
    avg_score: number
    topic_count: number
    topics: { topic: string; weighted_score: number; attempts: number; last_practiced: string | null }[]
    status: 'weak' | 'neutral' | 'strong'
  }[]
  weekly_summary: {
    period: string
    exercises: { count: number; avg_percent: number; correct: number; total_questions: number }
    flashcard_reviews: number
    study_minutes: number
    topics_practiced: number
    new_errors: number
  }
  error_summary: {
    total_errors: number
    pending_review: number
    top_error_topics: { topic: string; count: number }[]
  }
}

export async function getEnhancedDashboard(): Promise<EnhancedDashboard> {
  const res = await fetch(`${API}/api/stats/dashboard/enhanced`)
  if (!res.ok) throw new Error('Falha ao carregar dashboard avançado')
  return res.json()
}

// ── Tutor: Gamification ────────────────────────────────────────────────────────

export interface LevelInfo {
  level: string
  total_xp: number
  xp_to_next: number
  next_level: string | null
  progress_percent: number
  icon: string
}

export interface Leaderboard extends LevelInfo {
  achievements_earned: number
  total_achievements: number
  current_streak: number
  total_exercises: number
  total_flashcard_reviews: number
  topics_mastered: number
  weekly_xp: number
  recent_activity: { amount: number; source: string; description: string; created_at: string }[]
}

export async function getLevelInfo(): Promise<LevelInfo> {
  const res = await fetch(`${API}/api/level`)
  if (!res.ok) throw new Error('Falha ao carregar nível')
  return res.json()
}

export async function getLeaderboard(limit = 20): Promise<Leaderboard> {
  const res = await fetch(`${API}/api/leaderboard?limit=${limit}`)
  if (!res.ok) throw new Error('Falha ao carregar leaderboard')
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

// ── P8: Advanced Profile ──────────────────────────────────────────────────────

export async function startTime(type: string, metadata: Record<string, unknown> = {}): Promise<{ session_id: string }> {
  const res = await fetch(`${API}/api/sessions/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_type: type, metadata }),
  })
  if (!res.ok) throw new Error('Falha ao iniciar sessão')
  return res.json()
}

export async function endTime(sessionId: string): Promise<{ duration_seconds: number }> {
  const res = await fetch(`${API}/api/sessions/${sessionId}/end`, { method: 'POST' })
  if (!res.ok) throw new Error('Falha ao encerrar sessão')
  return res.json()
}

export interface TimeAnalytics {
  total_sessions: number
  total_study_minutes: number
  avg_session_minutes: number
  best_hours: { hour: number; sessions: number }[]
  by_type: Record<string, { count: number; avg_minutes: number }>
}

export async function getTimeAnalytics(): Promise<TimeAnalytics> {
  const res = await fetch(`${API}/api/stats/time-analytics`)
  if (!res.ok) throw new Error('Falha ao carregar analytics')
  return res.json()
}

export interface Recommendation {
  type: string
  description: string
  estimated_minutes: number
  priority: string
}

export async function getRecommendations(minutes: number): Promise<{ available_minutes: number; suggestions: Recommendation[] }> {
  const res = await fetch(`${API}/api/recommendations/${minutes}`)
  if (!res.ok) throw new Error('Falha ao carregar recomendações')
  return res.json()
}

export async function getDifficulty(topic: string) {
  const res = await fetch(`${API}/api/mastery/${topic}/difficulty`)
  if (!res.ok) throw new Error('Falha ao carregar dificuldade')
  return res.json()
}

// ── P9: Gamification ─────────────────────────────────────────────────────────

export interface Achievement {
  id: string
  title: string
  description: string
  icon: string
  category: string
  threshold: number
  earned: boolean
  earned_at: string | null
}

export interface AchievementProgress {
  locked: { id: string; title: string; icon: string; current: number; target: number; percent: number }[]
  total: number
  earned: number
}

export async function getAchievements(): Promise<Achievement[]> {
  const res = await fetch(`${API}/api/achievements`)
  if (!res.ok) throw new Error('Falha ao carregar conquistas')
  return res.json()
}

export async function getAchievementProgress(): Promise<AchievementProgress> {
  const res = await fetch(`${API}/api/achievements/progress`)
  if (!res.ok) throw new Error('Falha ao carregar progresso')
  return res.json()
}

export async function checkAchievements(): Promise<{ newly_earned: Achievement[] }> {
  const res = await fetch(`${API}/api/achievements/check`)
  if (!res.ok) throw new Error('Falha ao verificar conquistas')
  return res.json()
}

export interface TopicStreak {
  topic: string
  days_practiced: number
  current_streak: number
  last_practiced: string | null
}

export async function getTopicStreaks(): Promise<TopicStreak[]> {
  const res = await fetch(`${API}/api/streaks`)
  if (!res.ok) throw new Error('Falha ao carregar streaks')
  return res.json()
}

// ── P10: Export/Import ────────────────────────────────────────────────────────

export function exportDeckCsvUrl(deckId: string): string {
  return `${API}/api/flashcards/decks/${deckId}/export/csv`
}

export async function exportDeckJson(deckId: string) {
  const res = await fetch(`${API}/api/flashcards/decks/${deckId}/export/json`)
  if (!res.ok) throw new Error('Falha ao exportar deck')
  return res.json()
}

export async function importFlashcards(content: string, topic: string, title: string) {
  const res = await fetch(`${API}/api/flashcards/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, topic, title }),
  })
  if (!res.ok) throw new Error((await res.json()).detail || 'Falha ao importar')
  return res.json()
}

export function studyPlanExportUrl(planId: string): string {
  return `${API}/api/study-plans/${planId}/export`
}

export async function exportProfile() {
  const res = await fetch(`${API}/api/profile/export`)
  if (!res.ok) throw new Error('Falha ao exportar perfil')
  return res.json()
}

export async function importProfile(file: File) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API}/api/profile/import`, { method: 'POST', body: form })
  if (!res.ok) throw new Error((await res.json()).detail || 'Falha ao importar')
  return res.json()
}
