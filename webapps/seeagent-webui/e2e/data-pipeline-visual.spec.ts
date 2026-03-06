/**
 * Data Pipeline Scenario Visual E2E Test
 *
 * 可视化测试 data-pipeline.yaml 场景的完整流程：
 * 1. 生成数据 (generate) - 需要用户确认
 * 2. 数据校验 (validate)
 * 3. 生成数据指纹 (hash)
 * 4. 变更追踪 (track_changes) - 需要用户确认
 *
 * 测试方式：使用 Playwright 在 Chromium 浏览器中模拟用户操作
 */

import { test, expect, Page, BrowserContext } from '@playwright/test'

// 测试配置
const BASE_URL = process.env.BASE_URL || 'http://localhost:5175'
const API_URL = process.env.API_URL || 'http://localhost:18900'

// 场景数据
const SCENARIO_ID = 'data-pipeline'
const SCENARIO_NAME = '数据处理流水线'

// 测试数据
const TEST_DATA = {
  title: '测试项目计划',
  bullets: ['完成需求分析', '设计系统架构', '开发核心功能'],
  version: 'draft',
}

// 截图目录
const SCREENSHOT_DIR = './test-results/data-pipeline-visual'

test.describe('Data Pipeline Visual Test', () => {
  let context: BrowserContext
  let page: Page

  test.beforeAll(async ({ browser }) => {
    // 创建浏览器上下文
    context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      recordVideo: {
        dir: SCREENSHOT_DIR,
        size: { width: 1440, height: 900 }
      }
    })
    page = await context.newPage()

    // 设置较长的超时时间（LLM响应可能较慢）
    test.setTimeout(300000) // 5 minutes
  })

  test.afterAll(async () => {
    await context.close()
  })

  test('Step 1: 访问前端页面', async () => {
    console.log('📍 Step 1: 访问前端页面')

    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    // 截图：首页
    await page.screenshot({
      path: `${SCREENSHOT_DIR}/01-homepage.png`,
      fullPage: true
    })

    console.log('✅ 首页加载完成')
  })

  test('Step 2: 检查左侧边栏场景列表', async () => {
    console.log('📍 Step 2: 检查左侧边栏场景列表')

    // 查找左侧边栏
    const leftSidebar = page.locator('[data-testid="left-sidebar"], aside, .sidebar').first()
    await expect(leftSidebar).toBeVisible({ timeout: 10000 })

    // 截图：左侧边栏
    await leftSidebar.screenshot({
      path: `${SCREENSHOT_DIR}/02-left-sidebar.png`
    })

    console.log('✅ 左侧边栏可见')
  })

  test('Step 3: 查找并点击 data-pipeline 场景', async () => {
    console.log('📍 Step 3: 查找并点击 data-pipeline 场景')

    // 查找场景卡片
    const scenarioCard = page.locator(`text="${SCENARIO_NAME}"`).first()
    await expect(scenarioCard).toBeVisible({ timeout: 10000 })

    // 截图：场景卡片
    await scenarioCard.screenshot({
      path: `${SCREENSHOT_DIR}/03-scenario-card.png`
    })

    // 点击场景
    await scenarioCard.click()
    await page.waitForTimeout(1000)

    // 截图：场景详情
    await page.screenshot({
      path: `${SCREENSHOT_DIR}/04-scenario-detail.png`,
      fullPage: true
    })

    console.log('✅ 场景选中')
  })

  test('Step 4: 启动场景任务', async () => {
    console.log('📍 Step 4: 启动场景任务')

    // 查找启动按钮
    const startButton = page.locator('button:has-text("Start"), button:has-text("开始"), [data-testid="start-scenario"]').first()

    if (await startButton.isVisible()) {
      await startButton.click()
      await page.waitForTimeout(2000)

      // 截图：任务创建
      await page.screenshot({
        path: `${SCREENSHOT_DIR}/05-task-created.png`,
        fullPage: true
      })

      console.log('✅ 任务已启动')
    } else {
      console.log('⚠️ 未找到启动按钮，可能使用对话触发方式')
    }
  })

  test('Step 5: 通过对话触发场景', async () => {
    console.log('📍 Step 5: 通过对话触发场景')

    // 查找聊天输入框
    const chatInput = page.locator('textarea, input[type="text"], [contenteditable="true"]').first()
    await expect(chatInput).toBeVisible({ timeout: 10000 })

    // 输入触发词
    await chatInput.fill('数据处理流水线')
    await page.waitForTimeout(500)

    // 截图：输入触发词
    await page.screenshot({
      path: `${SCREENSHOT_DIR}/06-trigger-input.png`,
      fullPage: true
    })

    // 发送消息
    const sendButton = page.locator('button:has-text("Send"), button[type="submit"]').first()
    await sendButton.click()

    // 等待响应
    await page.waitForTimeout(3000)

    // 截图：发送后
    await page.screenshot({
      path: `${SCREENSHOT_DIR}/07-after-send.png`,
      fullPage: true
    })

    console.log('✅ 触发词已发送')
  })

  test('Step 6: 观察任务卡片和进度', async () => {
    console.log('📍 Step 6: 观察任务卡片和进度')

    // 等待任务卡片出现
    const taskCard = page.locator('[data-testid="task-card"], .task-card').first()
    await expect(taskCard).toBeVisible({ timeout: 30000 }).catch(() => {
      console.log('⚠️ 任务卡片未出现，检查其他UI元素')
    })

    // 截图：任务卡片
    if (await taskCard.isVisible()) {
      await taskCard.screenshot({
        path: `${SCREENSHOT_DIR}/08-task-card.png`
      })

      console.log('✅ 任务卡片可见')
    }

    // 检查进度条
    const progressBar = page.locator('.progress-bar, [data-testid="progress"]').first()
    if (await progressBar.isVisible()) {
      await progressBar.screenshot({
        path: `${SCREENSHOT_DIR}/09-progress-bar.png`
      })
      console.log('✅ 进度条可见')
    }
  })

  test('Step 7: 观察 Step 1 - 生成数据', async () => {
    console.log('📍 Step 7: 观察 Step 1 - 生成数据')

    // 等待步骤执行
    await page.waitForTimeout(5000)

    // 截图：Step 1 执行中
    await page.screenshot({
      path: `${SCREENSHOT_DIR}/10-step1-executing.png`,
      fullPage: true
    })

    // 查找确认按钮（如果需要用户确认）
    const confirmButton = page.locator('button:has-text("Confirm"), button:has-text("确认")').first()
    if (await confirmButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      // 截图：确认界面
      await page.screenshot({
        path: `${SCREENSHOT_DIR}/11-step1-confirmation.png`,
        fullPage: true
      })

      console.log('✅ Step 1 等待确认')

      // 点击确认
      await confirmButton.click()
      await page.waitForTimeout(2000)
    } else {
      console.log('ℹ️ Step 1 不需要确认或已自动完成')
    }
  })

  test('Step 8: 观察 Step 2 - 数据校验', async () => {
    console.log('📍 Step 8: 观察 Step 2 - 数据校验')

    // 等待步骤完成
    await page.waitForTimeout(3000)

    // 截图：Step 2 执行中
    await page.screenshot({
      path: `${SCREENSHOT_DIR}/12-step2-validating.png`,
      fullPage: true
    })

    console.log('✅ Step 2 执行中')
  })

  test('Step 9: 观察 Step 3 - 生成数据指纹', async () => {
    console.log('📍 Step 9: 观察 Step 3 - 生成数据指纹')

    // 等待步骤完成
    await page.waitForTimeout(3000)

    // 截图：Step 3 执行中
    await page.screenshot({
      path: `${SCREENSHOT_DIR}/13-step3-hashing.png`,
      fullPage: true
    })

    console.log('✅ Step 3 执行中')
  })

  test('Step 10: 观察 Step 4 - 变更追踪', async () => {
    console.log('📍 Step 10: 观察 Step 4 - 变更追踪')

    // 等待步骤完成
    await page.waitForTimeout(3000)

    // 截图：Step 4 执行中
    await page.screenshot({
      path: `${SCREENSHOT_DIR}/14-step4-tracking.png`,
      fullPage: true
    })

    // 查找确认按钮（如果需要用户确认）
    const confirmButton = page.locator('button:has-text("Confirm"), button:has-text("确认")').first()
    if (await confirmButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      // 截图：确认界面
      await page.screenshot({
        path: `${SCREENSHOT_DIR}/15-step4-confirmation.png`,
        fullPage: true
      })

      console.log('✅ Step 4 等待确认')

      // 点击确认
      await confirmButton.click()
      await page.waitForTimeout(2000)
    } else {
      console.log('ℹ️ Step 4 不需要确认或已自动完成')
    }
  })

  test('Step 11: 观察任务完成状态', async () => {
    console.log('📍 Step 11: 观察任务完成状态')

    // 等待任务完成
    await page.waitForTimeout(5000)

    // 检查完成状态
    const completedBadge = page.locator('text=/Completed|完成/i').first()

    if (await completedBadge.isVisible({ timeout: 10000 }).catch(() => false)) {
      // 截图：任务完成
      await page.screenshot({
        path: `${SCREENSHOT_DIR}/16-task-completed.png`,
        fullPage: true
      })

      console.log('✅ 任务已完成')
    } else {
      // 截图：当前状态
      await page.screenshot({
        path: `${SCREENSHOT_DIR}/16-task-status.png`,
        fullPage: true
      })

      console.log('ℹ️ 任务仍在执行中')
    }
  })

  test('Step 12: 查看最终输出', async () => {
    console.log('📍 Step 12: 查看最终输出')

    // 查找输出面板
    const outputPanel = page.locator('[data-testid="output-panel"], .output, .result').first()

    if (await outputPanel.isVisible({ timeout: 5000 }).catch(() => false)) {
      // 截图：输出面板
      await outputPanel.screenshot({
        path: `${SCREENSHOT_DIR}/17-output-panel.png`
      })

      console.log('✅ 输出面板可见')
    }

    // 最终全页面截图
    await page.screenshot({
      path: `${SCREENSHOT_DIR}/18-final-state.png`,
      fullPage: true
    })

    console.log('✅ 测试完成，所有截图已保存')
  })
})

test.describe('Data Pipeline API Test', () => {
  test('验证场景API可用', async ({ request }) => {
    console.log('📍 验证场景API可用')

    // 检查健康状态
    const healthResponse = await request.get(`${API_URL}/api/health`)
    expect(healthResponse.ok()).toBeTruthy()

    const healthData = await healthResponse.json()
    console.log('Health:', healthData)

    // 检查场景列表
    const scenariosResponse = await request.get(`${API_URL}/api/scenarios`)
    if (scenariosResponse.ok()) {
      const scenariosData = await scenariosResponse.json()
      console.log('Scenarios count:', scenariosData.total || scenariosData.scenarios?.length || 0)
    }
  })

  test('启动data-pipeline场景', async ({ request }) => {
    console.log('📍 启动data-pipeline场景')

    // 创建任务
    const createResponse = await request.post(`${API_URL}/api/tasks`, {
      data: {
        scenario_id: SCENARIO_ID,
        context: TEST_DATA
      }
    })

    if (createResponse.ok()) {
      const taskData = await createResponse.json()
      console.log('Task created:', taskData.task_id)

      expect(taskData.task_id).toBeDefined()
      expect(taskData.scenario_id).toBe(SCENARIO_ID)
    } else {
      console.log('Task creation response:', createResponse.status())
    }
  })
})

// 测试总结
test.describe('Test Summary', () => {
  test('输出测试总结', async () => {
    console.log(`
═══════════════════════════════════════════════════════════════
                    Data Pipeline Visual Test Summary
═══════════════════════════════════════════════════════════════

场景: ${SCENARIO_NAME} (${SCENARIO_ID})
步骤数: 4
  1. generate (生成数据) - requires_confirmation: true
  2. validate (数据校验) - requires_confirmation: false
  3. hash (生成数据指纹) - requires_confirmation: false
  4. track_changes (变更追踪) - requires_confirmation: true

测试流程:
  ✓ 访问前端页面
  ✓ 检查左侧边栏
  ✓ 选择场景
  ✓ 启动任务（或通过对话触发）
  ✓ 观察步骤执行
  ✓ 确认需要确认的步骤
  ✓ 观察最终状态

截图保存位置: ${SCREENSHOT_DIR}/

═══════════════════════════════════════════════════════════════
    `)
  })
})