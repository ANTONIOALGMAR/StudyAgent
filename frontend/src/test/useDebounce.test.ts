import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { useDebounce } from '../hooks/useDebounce'

describe('useDebounce', () => {
  it('returns initial value immediately', () => {
    const { result } = renderHook(() => useDebounce('hello', 500))
    expect(result.current).toBe('hello')
  })

  it('debounces value changes', async () => {
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: 'initial', delay: 500 } }
    )

    rerender({ value: 'updated', delay: 500 })
    expect(result.current).toBe('initial')

    await new Promise((r) => setTimeout(r, 600))
    expect(result.current).toBe('updated')
  })

  it('cancels previous timeout', async () => {
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: 'a', delay: 500 } }
    )

    rerender({ value: 'b', delay: 500 })
    await new Promise((r) => setTimeout(r, 200))
    rerender({ value: 'c', delay: 500 })
    await new Promise((r) => setTimeout(r, 400))
    expect(result.current).toBe('a')

    await new Promise((r) => setTimeout(r, 200))
    expect(result.current).toBe('c')
  })
})
