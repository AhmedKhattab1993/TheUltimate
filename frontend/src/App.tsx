import { SimpleStockScreener } from './components/SimpleStockScreener'
import { ScreenerProvider } from './contexts/ScreenerContext'
import { ErrorBoundary } from './components/ErrorBoundary'

function App() {
  return (
    <ErrorBoundary>
      <ScreenerProvider>
        <SimpleStockScreener />
      </ScreenerProvider>
    </ErrorBoundary>
  )
}

export default App
