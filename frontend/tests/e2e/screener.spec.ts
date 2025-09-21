import { test, expect } from '@playwright/test'

// Runs the full screener flow for a short date range and asserts UI results render
// along with a successful backend response.
test('simple screener flow renders results for selected period', async ({ page }) => {
  const startDateAriaLabel = 'Wednesday, September 10th, 2025'
  const endDateAriaLabel = 'Friday, September 12th, 2025'

  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Simple Stock Screener & Backtesting' })).toBeVisible()

  const startDateContainer = page.locator('label:has-text("Start Date")').locator('..')
  await startDateContainer.getByRole('button').click()
  const dayButtonProbe = page.locator('button[aria-label*="September"]')
  await dayButtonProbe.first().waitFor()
  let startDateButton = page.locator(`button[aria-label="${startDateAriaLabel}"]`).first()
  if ((await startDateButton.count()) === 0) {
    const nextMonthButton = page.getByRole('button', { name: /Go to the Next Month/i }).first()
    if (await nextMonthButton.isVisible()) {
      await nextMonthButton.click()
    }
    startDateButton = page.locator(`button[aria-label="${startDateAriaLabel}"]`).first()
  }
  await expect(startDateButton).toBeVisible()
  await startDateButton.click()

  const endDateContainer = page.locator('label:has-text("End Date")').locator('..')
  await endDateContainer.getByRole('button').click()
  const endDateButton = page.locator(`button[aria-label="${endDateAriaLabel}"]`).first()
  await expect(endDateButton).toBeVisible()
  await endDateButton.click()

  const runButton = page.getByRole('button', { name: /Run Screener/ })
  const responsePromise = page.waitForResponse((response) =>
    response.url().includes('/api/v2/simple-screener/screen') && response.request().method() === 'POST'
  )
  await runButton.click()
  const response = await responsePromise
  expect(response.ok()).toBeTruthy()

  const overlay = page.getByText('Screening in Progress...')
  await overlay.waitFor({ state: 'hidden' })

  await expect(page.getByRole('heading', { name: 'Screening Results' })).toBeVisible()
  const rows = page.locator('table tbody tr')
  await expect(rows.first()).toBeVisible()
  const firstSymbol = (await rows.first().locator('td').first().innerText()).trim()
  expect(firstSymbol.length).toBeGreaterThan(0)
  expect(firstSymbol).toMatch(/^[A-Z.\-]{1,6}$/)
})
