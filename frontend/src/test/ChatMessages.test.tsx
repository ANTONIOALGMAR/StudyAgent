import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import ChatMessages from '../components/ChatMessages'

describe('ChatMessages', () => {
  const baseProps = {
    messages: [] as { role: 'user' | 'assistant'; content: string }[],
    loading: false,
    handsFree: false,
    error: null,
  }

  it('shows welcome message when empty', () => {
    render(<ChatMessages {...baseProps} />)
    expect(screen.getByText('Olá! 👋')).toBeInTheDocument()
  })

  it('renders user and assistant messages', () => {
    const messages = [
      { role: 'user' as const, content: 'Olá' },
      { role: 'assistant' as const, content: 'Como posso ajudar?' },
    ]
    render(<ChatMessages {...baseProps} messages={messages} />)
    expect(screen.getByText('Olá')).toBeInTheDocument()
    expect(screen.getByText('Como posso ajudar?')).toBeInTheDocument()
  })

  it('shows thinking indicator when loading', () => {
    render(<ChatMessages {...baseProps} loading={true} />)
    expect(screen.getByText('pensando…')).toBeInTheDocument()
  })

  it('hides thinking indicator in hands-free mode', () => {
    render(<ChatMessages {...baseProps} loading={true} handsFree={true} />)
    expect(screen.queryByText('pensando…')).not.toBeInTheDocument()
  })

  it('shows error message', () => {
    render(<ChatMessages {...baseProps} error="Algo deu errado" />)
    expect(screen.getByText('⚠ Algo deu errado')).toBeInTheDocument()
  })
})
