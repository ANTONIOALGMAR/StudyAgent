import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useChat } from '../hooks/useChat'
import type { UploadedDoc } from '../api'

function respostaJson(body: unknown) {
  return {
    ok: true,
    json: async () => body,
  } as Response
}

describe('useChat — questões da tela e imagem anexada', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('resolve as questões da tela sob comando', async () => {
    ;(fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      respostaJson({
        monitor: 1,
        monitor_name: 'HDMI-1',
        screen_detected: true,
        ocr_available: true,
        ocr_length: 120,
        questions: [
          { label: '1', stem: 'Quanto é 3+4+5?', options: { a: '11', b: '12' }, kind: 'multipla_escolha', multiple_choice: true },
        ],
        answers: [{ label: '1', answer: 'B', answer_text: '12' }],
        answer_text: '1) B) 12',
      })
    )

    const { result } = renderHook(() =>
      useChat({ useScreen: false, liveOpen: false, monitorSel: 0, activeDoc: null })
    )

    await act(async () => {
      await result.current.solveScreenQuestions()
    })

    const ultima = result.current.messages[result.current.messages.length - 1]
    expect(ultima.content).toContain('tela 2')
    expect(ultima.content).toContain('tela sob comando')
    expect(ultima.content).toContain('1) B) 12')

    const chamada = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(chamada[0]).toContain('/api/screen/questions')
    expect(JSON.parse(chamada[1].body)).toEqual({
      monitor: null,
      question: null,
      session_id: null,
    })
  })

  it('avisa quando não há questões na tela', async () => {
    ;(fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      respostaJson({
        monitor: 0,
        screen_detected: false,
        ocr_available: true,
        ocr_length: 20,
        questions: [],
        answers: [],
        answer_text: 'Não encontrei questões',
      })
    )

    const { result } = renderHook(() =>
      useChat({ useScreen: false, liveOpen: false, monitorSel: 0, activeDoc: null })
    )

    await act(async () => {
      await result.current.solveScreenQuestions(2)
    })

    const ultima = result.current.messages[result.current.messages.length - 1]
    expect(ultima.content).toContain('Não encontrei questões')
    expect(ultima.content).toContain('tela não identificada')
  })

  it('trata foto de questão como imagem', async () => {
    ;(fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      respostaJson({ id: 'abc123', name: 'questao.png', pages: 1, chars: 240, kind: 'image' })
    )

    const { result } = renderHook(() =>
      useChat({ useScreen: false, liveOpen: false, monitorSel: 0, activeDoc: null })
    )

    const arquivo = new File(['x'], 'questao.png', { type: 'image/png' })
    let doc: UploadedDoc | null = null
    await act(async () => {
      doc = await result.current.loadDocument(arquivo)
    })

    expect((doc as UploadedDoc | null)?.kind).toBe('image')
    const ultima = result.current.messages[result.current.messages.length - 1]
    expect(ultima.content).toContain('questao.png')
    expect(ultima.content).toContain('resolva as questões')
  })
})