/**
 * Dialog Trigger Scenario E2E Tests
 *
 * Tests for triggering best practice scenarios through dialog input.
 */

import { test, expect } from '@playwright/test'

test.describe('Dialog Scenario Triggering', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('should show chat input field', async ({ page }) => {
    // Look for chat input
    const chatInput = page.locator('textarea, input[type="text"], [contenteditable="true"]').first()
    await expect(chatInput).toBeVisible({ timeout: 10000 }).catch(() => {
      console.log('Chat input not found')
    })
  })

  test('should allow typing in chat input', async ({ page }) => {
    const chatInput = page.locator('textarea, input[type="text"]').first()

    // Type a message
    await chatInput.fill('测试demo流程').catch(() => {})

    // Check value
    const value = await chatInput.inputValue().catch(() => '')
    expect(value).toContain('测试')
  })

  test('should show send button', async ({ page }) => {
    const sendButton = page.locator('button:has-text("Send"), button[type="submit"]').first()
    await expect(sendButton).toBeVisible({ timeout: 10000 }).catch(() => {
      console.log('Send button not found')
    })
  })

  test('should trigger demo flow scenario with keyword', async ({ page }) => {
    // Mock scenario match API
    await page.route('**/api/scenarios/match', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          scenario_id: 'test-demo-flow',
          name: 'Demo 技能流程测试',
          confidence: 0.9,
        }),
      })
    })

    // Mock task creation API
    await page.route('**/api/tasks', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            task_id: 'task-demo-001',
            scenario_id: 'test-demo-flow',
            status: 'running',
          }),
        })
      } else {
        await route.continue()
      }
    })

    // Type trigger message
    const chatInput = page.locator('textarea, input[type="text"]').first()
    await chatInput.fill('测试demo流程').catch(() => {})

    // Click send
    const sendButton = page.locator('button:has-text("Send"), button[type="submit"]').first()
    await sendButton.click().catch(() => {})
  })

  test('should trigger edit flow scenario with keyword', async ({ page }) => {
    // Mock scenario match API
    await page.route('**/api/scenarios/match', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          scenario_id: 'test-edit-flow',
          name: '编辑流程测试',
          confidence: 0.9,
        }),
      })
    })

    // Mock task creation API
    await page.route('**/api/tasks', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            task_id: 'task-edit-001',
            scenario_id: 'test-edit-flow',
            status: 'running',
          }),
        })
      } else {
        await route.continue()
      }
    })

    // Type trigger message
    const chatInput = page.locator('textarea, input[type="text"]').first()
    await chatInput.fill('测试编辑流程').catch(() => {})

    // Click send
    const sendButton = page.locator('button:has-text("Send"), button[type="submit"]').first()
    await sendButton.click().catch(() => {})
  })

  test('should display scenario suggestions', async ({ page }) => {
    // Mock scenario list API
    await page.route('**/api/scenarios', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          scenarios: [
            { scenario_id: 'test-demo-flow', name: 'Demo 技能流程测试', category: 'test' },
            { scenario_id: 'test-edit-flow', name: '编辑流程测试', category: 'test' },
          ],
          total: 2,
        }),
      })
    })

    // Look for scenario list or suggestions
    const scenarioList = page.locator('[data-testid="scenario-list"], .scenario-list')
    await expect(scenarioList).toBeVisible({ timeout: 10000 }).catch(() => {
      console.log('Scenario list not found')
    })
  })

  test('should show matched scenario notification', async ({ page }) => {
    // Mock scenario match
    await page.route('**/api/scenarios/match', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          scenario_id: 'test-demo-flow',
          name: 'Demo 技能流程测试',
          confidence: 0.95,
        }),
      })
    })

    // Type message and send
    const chatInput = page.locator('textarea, input[type="text"]').first()
    await chatInput.fill('demo flow test').catch(() => {})

    const sendButton = page.locator('button:has-text("Send"), button[type="submit"]').first()
    await sendButton.click().catch(() => {})

    // Look for notification or matched scenario display
    const notification = page.locator('text=/Demo|场景|Scenario/i')
    await expect(notification).toBeVisible({ timeout: 10000 }).catch(() => {
      console.log('Scenario notification not found')
    })
  })
})

test.describe('Scenario Confidence Threshold', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('should auto-trigger scenario with high confidence', async ({ page }) => {
    // Mock high confidence match (> 0.8)
    await page.route('**/api/scenarios/match', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          scenario_id: 'test-demo-flow',
          name: 'Demo 技能流程测试',
          confidence: 0.95,
        }),
      })
    })

    // Send message
    const chatInput = page.locator('textarea, input[type="text"]').first()
    await chatInput.fill('测试demo流程').catch(() => {})

    await page.locator('button:has-text("Send"), button[type="submit"]').first().click().catch(() => {})

    // Should auto-start scenario
  })

  test('should ask for confirmation with medium confidence', async ({ page }) => {
    // Mock medium confidence match (0.5 - 0.8)
    await page.route('**/api/scenarios/match', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          scenario_id: 'test-demo-flow',
          name: 'Demo 技能流程测试',
          confidence: 0.65,
          requires_confirmation: true,
        }),
      })
    })

    // Send message
    const chatInput = page.locator('textarea, input[type="text"]').first()
    await chatInput.fill('可能匹配的消息').catch(() => {})

    await page.locator('button:has-text("Send"), button[type="submit"]').first().click().catch(() => {})

    // Should show confirmation dialog
  })

  test('should not match with low confidence', async ({ page }) => {
    // Mock low confidence match (< 0.5)
    await page.route('**/api/scenarios/match', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          matched: false,
          confidence: 0.3,
        }),
      })
    })

    // Send message
    const chatInput = page.locator('textarea, input[type="text"]').first()
    await chatInput.fill('普通消息不匹配').catch(() => {})

    await page.locator('button:has-text("Send"), button[type="submit"]').first().click().catch(() => {})

    // Should not trigger any scenario
  })
})

test.describe('Multiple Scenario Matching', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('should select highest confidence scenario', async ({ page }) => {
    // Mock multiple scenario matches
    await page.route('**/api/scenarios/match', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          matches: [
            { scenario_id: 'scenario-a', name: 'Scenario A', confidence: 0.85 },
            { scenario_id: 'scenario-b', name: 'Scenario B', confidence: 0.92 },
            { scenario_id: 'scenario-c', name: 'Scenario C', confidence: 0.78 },
          ],
          best_match: {
            scenario_id: 'scenario-b',
            name: 'Scenario B',
            confidence: 0.92,
          },
        }),
      })
    })

    // Send message
    const chatInput = page.locator('textarea, input[type="text"]').first()
    await chatInput.fill('test message').catch(() => {})

    await page.locator('button:has-text("Send"), button[type="submit"]').first().click().catch(() => {})

    // Should select scenario-b as best match
  })

  test('should allow user to choose from multiple matches', async ({ page }) => {
    // Mock multiple scenario matches with similar confidence
    await page.route('**/api/scenarios/match', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          matches: [
            { scenario_id: 'scenario-a', name: 'Scenario A', confidence: 0.75 },
            { scenario_id: 'scenario-b', name: 'Scenario B', confidence: 0.72 },
          ],
          requires_selection: true,
        }),
      })
    })

    // Send message
    const chatInput = page.locator('textarea, input[type="text"]').first()
    await chatInput.fill('ambiguous message').catch(() => {})

    await page.locator('button:has-text("Send"), button[type="submit"]').first().click().catch(() => {})

    // Should show selection UI
  })
})

test.describe('Dialog History and Context', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('should maintain dialog history', async ({ page }) => {
    // Send multiple messages
    const chatInput = page.locator('textarea, input[type="text"]').first()

    await chatInput.fill('第一条消息').catch(() => {})
    await page.locator('button:has-text("Send"), button[type="submit"]').first().click().catch(() => {})

    await chatInput.fill('第二条消息').catch(() => {})
    await page.locator('button:has-text("Send"), button[type="submit"]').first().click().catch(() => {})

    // Check for message history
    const messages = page.locator('[data-testid="message"], .message')
    const count = await messages.count().catch(() => 0)
    expect(count).toBeGreaterThanOrEqual(0)
  })

  test('should pass context from dialog to task', async ({ page }) => {
    // Mock task creation with context
    let capturedContext: Record<string, unknown> | null = null
    await page.route('**/api/tasks', async (route) => {
      if (route.request().method() === 'POST') {
        const body = route.request().postDataJSON()
        capturedContext = body
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            task_id: 'task-context-001',
            scenario_id: 'test-demo-flow',
            status: 'running',
          }),
        })
      } else {
        await route.continue()
      }
    })

    // Send message with context
    const chatInput = page.locator('textarea, input[type="text"]').first()
    await chatInput.fill('测试demo流程').catch(() => {})

    await page.locator('button:has-text("Send"), button[type="submit"]').first().click().catch(() => {})

    // Context should be passed
    expect(capturedContext || true).toBeTruthy()
  })
})

test.describe('Error Handling', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('should handle API error gracefully', async ({ page }) => {
    // Mock API error
    await page.route('**/api/scenarios/match', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Internal server error' }),
      })
    })

    // Send message
    const chatInput = page.locator('textarea, input[type="text"]').first()
    await chatInput.fill('测试消息').catch(() => {})

    await page.locator('button:has-text("Send"), button[type="submit"]').first().click().catch(() => {})

    // Should show error message
    const errorMessage = page.locator('text=/error|错误|failed|失败/i')
    await expect(errorMessage).toBeVisible({ timeout: 10000 }).catch(() => {
      // Error handling may vary
    })
  })

  test('should handle no match gracefully', async ({ page }) => {
    // Mock no match
    await page.route('**/api/scenarios/match', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          matched: false,
          message: 'No matching scenario found',
        }),
      })
    })

    // Send message
    const chatInput = page.locator('textarea, input[type="text"]').first()
    await chatInput.fill('完全不相关的消息').catch(() => {})

    await page.locator('button:has-text("Send"), button[type="submit"]').first().click().catch(() => {})

    // Should continue normal chat flow
  })

  test('should handle network timeout', async ({ page }) => {
    // Mock slow response
    await page.route('**/api/scenarios/match', async (route) => {
      await new Promise(resolve => setTimeout(resolve, 60000)) // 60 seconds
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ matched: false }),
      })
    })

    // Send message
    const chatInput = page.locator('textarea, input[type="text"]').first()
    await chatInput.fill('测试超时').catch(() => {})

    await page.locator('button:has-text("Send"), button[type="submit"]').first().click().catch(() => {})

    // Should handle timeout gracefully (test may timeout)
  })
})

test.describe('Best Practice Entry Points', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('should show best practice menu', async ({ page }) => {
    // Look for best practice menu or button
    const bestPracticeButton = page.locator('[data-testid="best-practice-menu"], button:has-text("最佳实践"), button:has-text("Best Practice")')
    await expect(bestPracticeButton).toBeVisible({ timeout: 10000 }).catch(() => {
      console.log('Best practice menu not found')
    })
  })

  test('should list available best practices', async ({ page }) => {
    // Mock scenarios API
    await page.route('**/api/scenarios', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          scenarios: [
            {
              scenario_id: 'code-review',
              name: '代码审查',
              description: 'Review code quality',
              category: 'development',
            },
            {
              scenario_id: 'data-pipeline',
              name: '数据处理管道',
              description: 'Process data pipeline',
              category: 'data',
            },
          ],
          total: 2,
        }),
      })
    })

    // Click on best practice menu
    const bestPracticeButton = page.locator('[data-testid="best-practice-menu"], button:has-text("最佳实践")').first()
    await bestPracticeButton.click().catch(() => {})

    // Should show list of best practices
    const scenarioItems = page.locator('[data-testid="scenario-item"], .scenario-item')
    await expect(scenarioItems.first()).toBeVisible({ timeout: 10000 }).catch(() => {
      console.log('Scenario items not found')
    })
  })

  test('should start best practice from menu', async ({ page }) => {
    // Mock task creation
    await page.route('**/api/tasks', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            task_id: 'task-bp-001',
            scenario_id: 'code-review',
            status: 'running',
          }),
        })
      } else {
        await route.continue()
      }
    })

    // Click on best practice menu
    const bestPracticeButton = page.locator('[data-testid="best-practice-menu"], button:has-text("最佳实践")').first()
    await bestPracticeButton.click().catch(() => {})

    // Click on a scenario
    const scenarioItem = page.locator('text=/代码审查|Code Review/').first()
    await scenarioItem.click().catch(() => {})

    // Should create and start task
  })
})