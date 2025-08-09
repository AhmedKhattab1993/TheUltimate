import React, { ReactElement } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { ScreenerProvider } from '@/contexts/ScreenerContext'

interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  initialState?: any
}

const AllTheProviders = ({ children }: { children: React.ReactNode }) => {
  return <ScreenerProvider>{children}</ScreenerProvider>
}

const customRender = (
  ui: ReactElement,
  options?: CustomRenderOptions
) => render(ui, { wrapper: AllTheProviders, ...options })

// Re-export everything
export * from '@testing-library/react'
export { customRender as render }