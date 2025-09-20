import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useScreener } from './useScreener'
import { ScreenerProvider } from '@/contexts/ScreenerContext'
import { createElement, type ReactNode } from 'react'

const wrapper = ({ children }: { children: ReactNode }) => createElement(ScreenerProvider, null, children)

describe('useScreener', () => {
  const renderUseScreener = () => renderHook(() => useScreener(), { wrapper })

  it('initializes with default state', () => {
    const { result } = renderUseScreener()
    expect(result.current.isLoading).toBe(false)
    expect(result.current.error).toBeNull()
  })

  it('returns an error when run without configured dates', async () => {
    const { result } = renderUseScreener()

    await act(async () => {
      await result.current.runScreener()
    })

    expect(result.current.error).toBeTruthy()
    expect(result.current.isLoading).toBe(false)
  })
})
