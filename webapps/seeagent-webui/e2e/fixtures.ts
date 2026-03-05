/**
 * Playwright Test Fixtures
 *
 * Custom fixtures for E2E testing.
 */

import { test as base, expect, Page, BrowserContext } from '@playwright/test'

// Extend base test with custom fixtures
export const test = base.extend<{
  // Authenticated page fixture
  authenticatedPage: Page
  // Mocked API fixture
  mockApi: void
  // Test data fixture
  testData: TestData
}>({
  // Authenticated page - logs in before test
  authenticatedPage: async ({ page }, use) => {
    // Mock authentication if needed
    await page.goto('/')
    await use(page)
  },

  // Mock API responses
  mockApi: async ({ page }, use) => {
    // Setup common API mocks
    await page.route('**/api/health', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'healthy' }),
      })
    })

    await page.route('**/api/scenarios', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          scenarios: [
            {
              scenario_id: 'test-demo-flow',
              name: 'Demo 技能流程测试',
              description: 'Test demo skills flow',
              category: 'test',
              steps: [],
            },
          ],
          total: 1,
        }),
      })
    })

    await use()
  },

  // Test data
  testData: async ({}, use) => {
    const data: TestData = {
      mockTask: {
        task_id: 'test-task-001',
        scenario_id: 'test-demo-flow',
        scenario_name: 'Demo 技能流程测试',
        status: 'running',
        total_steps: 3,
        completed_steps: 1,
        steps: [
          { step_id: 'step-1', name: 'Step 1', status: 'completed' },
          { step_id: 'step-2', name: 'Step 2', status: 'running' },
          { step_id: 'step-3', name: 'Step 3', status: 'pending' },
        ],
      },
      mockScenario: {
        scenario_id: 'test-demo-flow',
        name: 'Demo 技能流程测试',
        description: 'Test demo skills flow',
        category: 'test',
        version: '1.0',
        steps: [
          { step_id: 'step-1', name: 'Step 1', description: 'First step' },
          { step_id: 'step-2', name: 'Step 2', description: 'Second step' },
          { step_id: 'step-3', name: 'Step 3', description: 'Third step' },
        ],
      },
    }
    await use(data)
  },
})

// Test data types
export interface TestData {
  mockTask: MockTask
  mockScenario: MockScenario
}

export interface MockTask {
  task_id: string
  scenario_id: string
  scenario_name: string
  status: string
  total_steps: number
  completed_steps: number
  steps: MockStep[]
}

export interface MockStep {
  step_id: string
  name: string
  status?: string
  description?: string
}

export interface MockScenario {
  scenario_id: string
  name: string
  description: string
  category: string
  version: string
  steps: MockStep[]
}

// Export expect for convenience
export { expect }

// Helper functions
export async function waitForApiReady(page: Page, timeout = 30000): Promise<boolean> {
  try {
    const response = await page.waitForResponse(
      (res) => res.url().includes('/api/health') && res.status() === 200,
      { timeout }
    )
    return response.status() === 200
  } catch {
    return false
  }
}

export async function mockTaskApi(page: Page, task: MockTask): Promise<void> {
  await page.route(`**/api/tasks/${task.task_id}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(task),
    })
  })
}

export async function mockScenarioApi(page: Page, scenarios: MockScenario[]): Promise<void> {
  await page.route('**/api/scenarios', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        scenarios,
        total: scenarios.length,
      }),
    })
  })
}

export async function createTestTask(page: Page, scenarioId: string): Promise<string> {
  const response = await page.request.post('/api/tasks', {
    data: { scenario_id: scenarioId },
  })

  const data = await response.json()
  return data.task_id
}

export async function deleteTestTask(page: Page, taskId: string): Promise<void> {
  await page.request.post(`/api/tasks/${taskId}/cancel`)
}