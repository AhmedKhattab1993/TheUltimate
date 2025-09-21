import { test, expect, Page } from '@playwright/test'
import { format } from 'date-fns'
import { spawnSync } from 'node:child_process'

const START_DATE_ISO = '2025-02-12'
const END_DATE_ISO = '2025-02-13'
const DATE_RANGE_DISPLAY = `${format(new Date(2025, 1, 12), 'MMM dd')} - ${format(new Date(2025, 1, 13), 'MMM dd, yyyy')}`
const SYMBOLS = ['AAPL', 'MSFT']
const DB_URL = 'postgresql://postgres:postgres@localhost:5432/stock_screener'

async function waitForBacktestCompletion(page: Page, backtestId: string) {
  const timeoutMs = 10 * 60 * 1000
  const started = Date.now()

  while (Date.now() - started < timeoutMs) {
    const response = await page.request.get(`http://localhost:8000/api/v2/backtest/status/${backtestId}`)
    expect(response.ok()).toBeTruthy()
    const payload = await response.json()

    if (payload.status === 'completed') {
      return payload
    }
    if (payload.status === 'failed') {
      throw new Error(`Backtest ${backtestId} failed: ${payload.error_message ?? 'unknown error'}`)
    }
    if (payload.status === 'cancelled') {
      throw new Error(`Backtest ${backtestId} was cancelled`)
    }

    await page.waitForTimeout(2000)
  }

  throw new Error(`Backtest ${backtestId} did not complete within timeout`)
}

function fetchBacktestSymbols(runId: string) {
  const sanitized = runId.replace(/[^0-9a-fA-F-]/g, '')
  if (sanitized !== runId) {
    throw new Error('Unexpected characters in run identifier')
  }

  const sql = `SELECT symbol, status FROM backtest_results WHERE run_id = '${sanitized}' ORDER BY symbol;`
  const result = spawnSync('psql', [
    DB_URL,
    '-t',
    '-A',
    '-F', ',',
    '-c',
    sql,
  ], { encoding: 'utf-8' })

  if (result.error) {
    throw result.error
  }
  if (result.status !== 0) {
    throw new Error(`psql exited with code ${result.status}: ${result.stderr}`)
  }

  return result.stdout
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [symbol, status] = line.split(',').map((part) => part.trim())
      return { symbol, status }
    })
}

test('manual backtest across multiple days persists results to UI and DB', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Simple Stock Screener & Backtesting' })).toBeVisible()

  await page.route('**/api/v2/backtest/run**', async (route, request) => {
    if (request.method() !== 'POST') {
      await route.continue()
      return
    }
    const rawBody = request.postData() ?? '{}'
    let payload
    try {
      payload = JSON.parse(rawBody)
    } catch {
      payload = {}
    }
    payload.start_date = '2025-02-12'
    payload.end_date = '2025-02-13'
    await route.continue({ postData: JSON.stringify(payload) })
  })

  await page.getByRole('tab', { name: 'Backtesting' }).click()
  const backtestingPanel = page.getByRole('tabpanel', { name: 'Backtesting' })
  await expect(backtestingPanel.getByRole('heading', { name: 'Backtesting' })).toBeVisible()

  const strategyOption = backtestingPanel.getByLabel('Market Structure')
  await expect(strategyOption).toBeVisible()
  await strategyOption.click()

  const pivotInput = backtestingPanel.getByLabel('Pivot Bars')
  await pivotInput.fill('2')

  const lowerTimeframeSelector = backtestingPanel.locator('#lower-timeframe')
  await lowerTimeframeSelector.click()
  await page.getByRole('option', { name: '1 Minute' }).click()

  const screenerCheckbox = backtestingPanel.getByRole('checkbox', { name: 'Use latest screener results' })
  await expect(screenerCheckbox).not.toBeChecked()

  for (const symbol of SYMBOLS) {
    const symbolInput = backtestingPanel.getByPlaceholder('Enter symbol (e.g., AAPL)')
    await symbolInput.fill(symbol)
    await symbolInput.press('Enter')
    await expect(backtestingPanel.getByText(symbol, { exact: true })).toBeVisible()
  }

  const runButton = backtestingPanel.getByRole('button', { name: /^Run Backtest$/ })
  const runResponsePromise = page.waitForResponse((response) =>
    response.url().includes('http://localhost:8000/api/v2/backtest/run') &&
    response.request().method() === 'POST'
  )

  await runButton.click()

  const runResponse = await runResponsePromise
  const responseText = await runResponse.text()
  if (!runResponse.ok()) {
    throw new Error(`Backtest request failed (${runResponse.status()}): ${responseText}`)
  }
  const runPayload = JSON.parse(responseText) as {
    backtest_id: string
    request?: { start_date?: string; end_date?: string }
  }
  const backtestId = runPayload.backtest_id
  expect(backtestId).toMatch(/^[0-9a-fA-F-]{36}$/)
  expect(runPayload.request?.start_date).toBe(START_DATE_ISO)
  expect(runPayload.request?.end_date).toBe(END_DATE_ISO)

  await expect(backtestingPanel.getByText('Running backtests...')).toBeVisible()

  await waitForBacktestCompletion(page, backtestId)

  await expect(backtestingPanel.getByText('Running backtests...')).not.toBeVisible({ timeout: 180000 })
  await expect(runButton).toBeEnabled()
  await expect(runButton).toHaveText('Run Backtest')

  const results = fetchBacktestSymbols(backtestId)
  expect(results.length).toBeGreaterThanOrEqual(2)
  const storedSymbols = new Set(results.map((entry) => entry.symbol))
  for (const symbol of SYMBOLS) {
    expect(storedSymbols.has(symbol)).toBeTruthy()
  }
  results.forEach((entry) => {
    expect(entry.status).toBe('completed')
  })

  await page.getByRole('tab', { name: 'Results', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Results History' })).toBeVisible()
  await page.waitForTimeout(4000)
  await page.getByRole('tab', { name: 'Backtest Results', exact: true }).click()
  await page.waitForTimeout(1000)

  const resultsCard = page
    .getByRole('heading', { name: 'Comprehensive Backtest Results' })
    .locator('..')
    .locator('..')

  const summaryRow = resultsCard.locator('table tbody tr', { hasText: DATE_RANGE_DISPLAY }).first()
  await summaryRow.waitFor({ state: 'visible', timeout: 60000 })
  await expect(summaryRow).toContainText(DATE_RANGE_DISPLAY)
  await expect(summaryRow).toContainText('1min')
  await expect(summaryRow).toContainText('2')
})
