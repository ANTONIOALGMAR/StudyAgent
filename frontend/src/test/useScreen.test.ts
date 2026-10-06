import { useState } from 'react'
import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useScreen } from '../hooks/useScreen'
import { detectScreenQuestions, answerScreenQuestions } from '../api'

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api')>()
  return {
    ...actual,
    detectScreenQuestions: vi.fn(),
    answerScreenQuestions: vi.fn(),
    getMonitors: vi.fn().mockResolvedValue([]),
    chat: vi.fn(),
    captureScreen: vi.fn(),
  }
})

const detect = detectScreenQuestions as ReturnType<typeof vi.fn>
const answer = answerScreenQuestions as ReturnType<typeof vi.fn>

const QUESTAO = {
  label: '1',
  stem: 'Quanto é 3+4+5?',
  options: { a: '11', b: '12' },
  kind: 'multipla_escolha',
  multiple_choice: true,
  fingerprint: 'fp-questao-1',
}

function detectResposta() {
  return {
    session_id: null,
    monitor: 0,
    monitor_name: null,
    screen_detected: false,
    window: null,
    ocr_available: true,
    ocr_length: 120,
    fingerprint: 'fp-tela',
    questions: [QUESTAO],
  }
}

function answerResposta() {
  return {
    session_id: 'sess-1',
    monitor: 0,
    monitor_name: null,
    screen_detected: false,
    window: null,
    ocr_available: true,
    ocr_length: 120,
    questions: [QUESTAO],
    answers: [{ label: '1', answer: 'B', answer_text: '12' }],
    answer_text: '1) B) 12 — 3+4+5 = 12.',
  }
}

describe('useScreen — auto-solve de questões ao vivo', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    detect.mockReset()
    answer.mockReset()
    detect.mockResolvedValue(detectResposta())
    answer.mockResolvedValue(answerResposta())
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  function renderScreen() {
    const sessionIdRef = { current: null as string | null }
    const setSessionId = vi.fn()
    const hook = renderHook(() => {
      const [messages, setMessages] = useState<
        { role: 'user' | 'assistant'; content: string }[]
      >([])
      const screen = useScreen({ sessionIdRef, setMessages, setSessionId })
      return { screen, messages }
    })
    return { ...hook, sessionIdRef, setSessionId }
  }

  it('resolve questões novas uma única vez e ignora as repetidas', async () => {
    const { result } = renderScreen()

    await act(async () => {
      result.current.screen.setLiveOpen(true)
      result.current.screen.setAutoSolve(true)
      await vi.advanceTimersByTimeAsync(10)
    })

    // Detectou e resolveu na primeira varredura
    expect(detect).toHaveBeenCalledTimes(1)
    expect(answer).toHaveBeenCalledTimes(1)
    expect(answer).toHaveBeenCalledWith(0, null, null, expect.any(AbortSignal))

    const msgs = result.current.messages
    expect(msgs).toHaveLength(2)
    expect(msgs[0].content).toContain('Resolva as questões')
    expect(msgs[1].content).toContain('resolvida automaticamente')
    expect(msgs[1].content).toContain('1) B) 12')

    // Próximas varreduras: mesma questão na tela → não repete a resolução
    await act(async () => {
      await vi.advanceTimersByTimeAsync(11000)
    })
    expect(detect.mock.calls.length).toBeGreaterThanOrEqual(3)
    expect(answer).toHaveBeenCalledTimes(1)
  })

  it('questões diferentes na tela disparam nova resolução', async () => {
    const { result } = renderScreen()

    await act(async () => {
      result.current.screen.setLiveOpen(true)
      result.current.screen.setAutoSolve(true)
      await vi.advanceTimersByTimeAsync(10)
    })
    expect(answer).toHaveBeenCalledTimes(1)

    detect.mockResolvedValue({
      ...detectResposta(),
      fingerprint: 'fp-tela-2',
      questions: [{ ...QUESTAO, label: '2', stem: 'Qual a capital?', fingerprint: 'fp-questao-2' }],
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(6000)
    })
    expect(answer).toHaveBeenCalledTimes(2)
  })

  it('desligar e religar limpa a memória de questões vistas', async () => {
    const { result } = renderScreen()

    await act(async () => {
      result.current.screen.setLiveOpen(true)
      result.current.screen.setAutoSolve(true)
      await vi.advanceTimersByTimeAsync(10)
    })
    expect(answer).toHaveBeenCalledTimes(1)

    await act(async () => {
      result.current.screen.setAutoSolve(false)
      await vi.advanceTimersByTimeAsync(10)
    })

    await act(async () => {
      result.current.screen.setAutoSolve(true)
      await vi.advanceTimersByTimeAsync(10)
    })
    expect(answer).toHaveBeenCalledTimes(2)
  })

  it('sem auto-solve ligado não varre a tela', async () => {
    const { result } = renderScreen()

    await act(async () => {
      result.current.screen.setLiveOpen(true)
      await vi.advanceTimersByTimeAsync(10000)
    })

    expect(detect).not.toHaveBeenCalled()
    expect(answer).not.toHaveBeenCalled()
  })

  it('fecha o loop quando o painel é fechado', async () => {
    const { result } = renderScreen()

    await act(async () => {
      result.current.screen.setLiveOpen(true)
      result.current.screen.setAutoSolve(true)
      await vi.advanceTimersByTimeAsync(10)
    })
    expect(detect).toHaveBeenCalledTimes(1)

    // Fecha primeiro (render + effects rodam), depois avança o tempo —
    // senão o loop continuaria varrendo durante o avanço sintético.
    await act(async () => {
      result.current.screen.setLiveOpen(false)
    })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(11000)
    })

    // Só a varredura inicial; nada depois de fechar o painel
    expect(detect).toHaveBeenCalledTimes(1)
    expect(answer).toHaveBeenCalledTimes(1)
  })
})
