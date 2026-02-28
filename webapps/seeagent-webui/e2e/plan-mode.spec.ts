import { test, expect } from '@playwright/test'

/**
 * E2E Tests for Plan Mode UI
 *
 * These tests verify the complete Plan mode flow including:
 * - Plan creation and display
 * - Step execution and status updates
 * - ask_user interaction and context preservation
 * - PlanCard animations and visual feedback
 */

test.describe('Plan Mode', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    // Wait for the page to load
    await expect(page.locator('text=SeeAgent')).toBeVisible()
  })

  test('should create and display plan card', async ({ page }) => {
    // Create a new chat
    await page.click('button:has-text("New Chat")')

    // Fill in a task that triggers plan creation
    const textarea = page.locator('textarea')
    await textarea.fill('请打开百度网站，搜索北京今天天气，然后截图保存')

    // Send the message
    await page.click('button:has-text("send")')

    // Wait for plan card to appear (with extended timeout for LLM response)
    // Use a more specific selector for the heading
    const planCardHeading = page.locator('h3:has-text("任务计划")')
    await expect(planCardHeading).toBeVisible({ timeout: 90000 })

    // Verify task summary is displayed
    const taskSummary = page.locator('text=/百度|天气|截图/')
    await expect(taskSummary.first()).toBeVisible()
  })

  test('should display plan steps with correct status icons', async ({ page }) => {
    // Create a new chat
    await page.click('button:has-text("New Chat")')

    // Fill in a task
    const textarea = page.locator('textarea')
    await textarea.fill('请打开百度网站，搜索北京今天天气，然后截图保存')

    // Send the message
    await page.click('button:has-text("send")')

    // Wait for plan card
    await expect(page.locator('h3:has-text("任务计划")')).toBeVisible({ timeout: 90000 })

    // Check for step status icons (pending: ⏳, in_progress: ▶️, completed: ✅)
    const pendingIcon = page.locator('text=⏳')
    const inProgressIcon = page.locator('text=▶️')
    const completedIcon = page.locator('text=✅')

    // At least one of these should be visible depending on execution state
    const hasStatusIcon =
      (await pendingIcon.count()) > 0 ||
      (await inProgressIcon.count()) > 0 ||
      (await completedIcon.count()) > 0

    expect(hasStatusIcon).toBe(true)
  })

  test('should update progress bar during execution', async ({ page }) => {
    // Create a new chat
    await page.click('button:has-text("New Chat")')

    // Fill in a task
    const textarea = page.locator('textarea')
    await textarea.fill('请打开百度网站，搜索北京今天天气，然后截图保存')

    // Send the message
    await page.click('button:has-text("send")')

    // Wait for plan card
    await expect(page.locator('h3:has-text("任务计划")')).toBeVisible({ timeout: 90000 })

    // Check for progress indicator
    const progressText = page.locator('text=/进度: \\d+\\/\\d+ 完成/')
    await expect(progressText).toBeVisible({ timeout: 90000 })

    // Verify percentage is displayed
    const percentText = page.locator('text=/\\d+%/')
    await expect(percentText).toBeVisible()
  })

  test('should handle ask_user interaction', async ({ page }) => {
    // Create a new chat
    await page.click('button:has-text("New Chat")')

    // Fill in a task that might trigger ask_user
    const textarea = page.locator('textarea')
    await textarea.fill('请帮我查询今天的天气')

    // Send the message
    await page.click('button:has-text("send")')

    // Wait for either ask_user or plan card
    const askUserSection = page.locator('text=需要确认')
    const planCardHeading = page.locator('h3:has-text("任务计划")')

    // Either ask_user or plan should appear (with extended timeout)
    try {
      await expect(askUserSection).toBeVisible({ timeout: 90000 })
    } catch {
      // If ask_user doesn't appear, check for plan card
      await expect(planCardHeading).toBeVisible({ timeout: 90000 })
      return
    }

    // If ask_user appeared, click an option
    if (await askUserSection.isVisible()) {
      const optionButton = page.locator('button').filter({ hasText: /^(北京|上海|广州|深圳)$/ }).first()
      if (await optionButton.isVisible()) {
        await optionButton.click()

        // Verify the response is processed
        await page.waitForTimeout(2000)
      }
    }
  })

  test('should show completed state with success message', async ({ page }) => {
    // Create a new chat
    await page.click('button:has-text("New Chat")')

    // Fill in a simple task
    const textarea = page.locator('textarea')
    await textarea.fill('请打开百度网站，搜索北京今天天气，然后截图保存')

    // Send the message
    await page.click('button:has-text("send")')

    // Wait for plan card
    await expect(page.locator('text=任务计划')).toBeVisible({ timeout: 60000 })

    // Wait for completion (either 100% progress or completed icon)
    const completedIcon = page.locator('text=🎉')
    const progress100 = page.locator('text=100%')
    const taskCompleted = page.locator('text=任务已完成')

    // Wait for any completion indicator (with extended timeout)
    await Promise.race([
      expect(completedIcon).toBeVisible({ timeout: 180000 }),
      expect(progress100).toBeVisible({ timeout: 180000 }),
      expect(taskCompleted).toBeVisible({ timeout: 180000 }),
    ])
  })

  test('should have plan card with slide-in animation', async ({ page }) => {
    // Create a new chat
    await page.click('button:has-text("New Chat")')

    // Fill in a task
    const textarea = page.locator('textarea')
    await textarea.fill('请打开百度网站，搜索北京今天天气，然后截图保存')

    // Send the message
    await page.click('button:has-text("send")')

    // Wait for plan card
    const planCard = page.locator('text=任务计划').locator('xpath=ancestor::div[contains(@class, "animate-slide-in")]')

    // The plan card should have the animation class
    await expect(planCard).toBeVisible({ timeout: 60000 })
  })
})

test.describe('Plan Mode - Error Handling', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('text=SeeAgent')).toBeVisible()
  })

  test('should display step cards during execution', async ({ page }) => {
    // Create a new chat
    await page.click('button:has-text("New Chat")')

    // Fill in a task
    const textarea = page.locator('textarea')
    await textarea.fill('请打开百度网站，搜索北京今天天气，然后截图保存')

    // Send the message
    await page.click('button:has-text("send")')

    // Wait for step cards to appear (they have check_circle or other icons)
    const stepCard = page.locator('[data-material-icon], .material-symbols-outlined').first()
    await expect(stepCard).toBeVisible({ timeout: 60000 })
  })
})
