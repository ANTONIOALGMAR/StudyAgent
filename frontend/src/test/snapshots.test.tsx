import { render } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import ChatMessages from '../components/ChatMessages'
import ChatInput from '../components/ChatInput'
import LivePanel from '../components/LivePanel'

describe('ChatMessages snapshots', () => {
  const baseProps = {
    messages: [] as { role: 'user' | 'assistant'; content: string }[],
    loading: false,
    handsFree: false,
    error: null,
  }

  it('renders welcome state', () => {
    const { container } = render(<ChatMessages {...baseProps} />)
    expect(container).toMatchSnapshot()
  })

  it('renders with messages', () => {
    const messages = [
      { role: 'user' as const, content: 'Olá' },
      { role: 'assistant' as const, content: 'Como posso ajudar?' },
    ]
    const { container } = render(<ChatMessages {...baseProps} messages={messages} />)
    expect(container).toMatchSnapshot()
  })

  it('renders loading state', () => {
    const { container } = render(<ChatMessages {...baseProps} loading={true} />)
    expect(container).toMatchSnapshot()
  })

  it('renders error state', () => {
    const { container } = render(<ChatMessages {...baseProps} error="Erro teste" />)
    expect(container).toMatchSnapshot()
  })
})

describe('ChatInput snapshots', () => {
  const baseProps = {
    input: '',
    setInput: () => {},
    onSend: () => {},
    onToggleRecording: () => {},
    recording: false,
    loading: false,
    handsFree: false,
    voiceOn: true,
    setVoiceOn: () => {},
    onStartHandsFree: () => {},
    onStopHandsFree: () => {},
    onFileChosen: () => {},
  }

  it('renders default state', () => {
    const { container } = render(<ChatInput {...baseProps} />)
    expect(container).toMatchSnapshot()
  })

  it('renders with text input', () => {
    const { container } = render(<ChatInput {...baseProps} input="Olá mundo" />)
    expect(container).toMatchSnapshot()
  })

  it('renders recording state', () => {
    const { container } = render(<ChatInput {...baseProps} recording={true} />)
    expect(container).toMatchSnapshot()
  })

  it('renders hands-free state', () => {
    const { container } = render(<ChatInput {...baseProps} handsFree={true} />)
    expect(container).toMatchSnapshot()
  })
})

describe('LivePanel snapshots', () => {
  const baseProps = {
    monitors: [{ index: 0, width: 1920, height: 1080, left: 0, top: 0 }],
    monitorSel: 0,
    setMonitorSel: () => {},
    previewTick: 0,
    watchMode: false,
    setWatchMode: () => {},
    onClose: () => {},
    onMinimize: () => {},
  }

  it('renders default state', () => {
    const { container } = render(<LivePanel {...baseProps} />)
    expect(container).toMatchSnapshot()
  })

  it('renders with watch mode enabled', () => {
    const { container } = render(<LivePanel {...baseProps} watchMode={true} />)
    expect(container).toMatchSnapshot()
  })
})
