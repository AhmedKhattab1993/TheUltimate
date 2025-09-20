import type { ReactElement, ReactNode } from 'react'
import { render } from '@testing-library/react'
import type { RenderOptions } from '@testing-library/react'
import { AppProviders } from '@/app/AppProviders'

interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  initialState?: any
}

const AllTheProviders = ({ children }: { children: ReactNode }) => {
  return <AppProviders>{children}</AppProviders>
}

const customRender = (
  ui: ReactElement,
  options?: CustomRenderOptions
) => render(ui, { wrapper: AllTheProviders, ...options })

// Re-export everything
export * from '@testing-library/react'
export { customRender as render }
