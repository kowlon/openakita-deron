/**
 * Test Helper Functions
 *
 * Utility functions for E2E testing.
 */

import { Page, Locator, expect } from '@playwright/test'

/**
 * Wait for element to be visible with custom timeout
 */
export async function waitForElement(
  page: Page,
  selector: string,
  timeout = 10000
): Promise<Locator> {
  const element = page.locator(selector)
  await expect(element).toBeVisible({ timeout })
  return element
}

/**
 * Wait for API response
 */
export async function waitForApiResponse(
  page: Page,
  pathPattern: string,
  timeout = 30000
): Promise<Response | null> {
  try {
    return await page.waitForResponse(
      (response) => response.url().includes(pathPattern),
      { timeout }
    )
  } catch {
    return null
  }
}

/**
 * Mock API response
 */
export async function mockApi(
  page: Page,
  path: string,
  response: object,
  status = 200
): Promise<void> {
  await page.route(`**${path}*`, async (route) => {
    await route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify(response),
    })
  })
}

/**
 * Clear all mock routes
 */
export async function clearMocks(page: Page): Promise<void> {
  await page.unrouteAll()
}

/**
 * Take screenshot with timestamp
 */
export async function takeScreenshot(
  page: Page,
  name: string
): Promise<void> {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-')
  await page.screenshot({
    path: `test-results/${name}-${timestamp}.png`,
  })
}

/**
 * Generate random string
 */
export function randomString(length = 8): string {
  return Math.random().toString(36).substring(2, length + 2)
}

/**
 * Generate test task ID
 */
export function generateTaskId(): string {
  return `test-task-${randomString(8)}`
}

/**
 * Generate test scenario ID
 */
export function generateScenarioId(): string {
  return `test-scenario-${randomString(8)}`
}

/**
 * Login helper (if authentication is needed)
 */
export async function login(
  page: Page,
  username: string,
  password: string
): Promise<void> {
  // Navigate to login page if needed
  // Fill credentials
  // Submit form
  // Wait for redirect
}

/**
 * Logout helper
 */
export async function logout(page: Page): Promise<void> {
  // Click logout button
  // Wait for redirect
}

/**
 * Wait for loading to complete
 */
export async function waitForLoading(
  page: Page,
  timeout = 30000
): Promise<void> {
  // Wait for loading indicators to disappear
  const loadingSelectors = [
    '.loading',
    '[data-testid="loading"]',
    '.spinner',
    '.skeleton',
  ]

  for (const selector of loadingSelectors) {
    try {
      await page.waitForSelector(selector, { state: 'hidden', timeout })
    } catch {
      // Selector may not exist
    }
  }
}

/**
 * Check if element is in viewport
 */
export async function isInViewport(
  page: Page,
  selector: string
): Promise<boolean> {
  const element = page.locator(selector)
  return await element.evaluate((el) => {
    const rect = el.getBoundingClientRect()
    return (
      rect.top >= 0 &&
      rect.left >= 0 &&
      rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
      rect.right <= (window.innerWidth || document.documentElement.clientWidth)
    )
  })
}

/**
 * Scroll element into view
 */
export async function scrollIntoView(
  page: Page,
  selector: string
): Promise<void> {
  await page.locator(selector).scrollIntoViewIfNeeded()
}

/**
 * Get element text content
 */
export async function getTextContent(
  page: Page,
  selector: string
): Promise<string> {
  return await page.locator(selector).textContent() || ''
}

/**
 * Check if element exists
 */
export async function elementExists(
  page: Page,
  selector: string
): Promise<boolean> {
  const count = await page.locator(selector).count()
  return count > 0
}

/**
 * Wait for navigation to complete
 */
export async function waitForNavigation(
  page: Page,
  expectedUrl: string
): Promise<void> {
  await page.waitForURL(`**${expectedUrl}**`, { timeout: 30000 })
}

/**
 * Mock SSE stream
 */
export async function mockSSE(
  page: Page,
  path: string,
  events: object[]
): Promise<void> {
  await page.route(`**${path}*`, async (route) => {
    const sseData = events
      .map((event) => `data: ${JSON.stringify(event)}\n\n`)
      .join('')

    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: sseData,
    })
  })
}

/**
 * Simulate network offline
 */
export async function goOffline(page: Page): Promise<void> {
  await page.context().setOffline(true)
}

/**
 * Simulate network online
 */
export async function goOnline(page: Page): Promise<void> {
  await page.context().setOffline(false)
}

/**
 * Get localStorage item
 */
export async function getLocalStorageItem(
  page: Page,
  key: string
): Promise<string | null> {
  return await page.evaluate((k) => {
    return localStorage.getItem(k)
  }, key)
}

/**
 * Set localStorage item
 */
export async function setLocalStorageItem(
  page: Page,
  key: string,
  value: string
): Promise<void> {
  await page.evaluate(
    ({ k, v }) => {
      localStorage.setItem(k, v)
    },
    { k: key, v: value }
  )
}

/**
 * Clear localStorage
 */
export async function clearLocalStorage(page: Page): Promise<void> {
  await page.evaluate(() => {
    localStorage.clear()
  })
}

/**
 * Resize window
 */
export async function resizeWindow(
  page: Page,
  width: number,
  height: number
): Promise<void> {
  await page.setViewportSize({ width, height })
}

/**
 * Mobile viewport sizes
 */
export const MOBILE_VIEWPORTS = {
  iPhone: { width: 375, height: 667 },
  iPhonePlus: { width: 414, height: 736 },
  iPad: { width: 768, height: 1024 },
  iPadPro: { width: 1024, height: 1366 },
}

/**
 * Desktop viewport sizes
 */
export const DESKTOP_VIEWPORTS = {
  laptop: { width: 1366, height: 768 },
  desktop: { width: 1440, height: 900 },
  largeDesktop: { width: 1920, height: 1080 },
}