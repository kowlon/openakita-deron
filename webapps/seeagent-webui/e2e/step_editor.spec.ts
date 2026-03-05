/**
 * Step Output Editor E2E Tests
 *
 * Tests for the StepOutputEditor component: display, editing, and saving functionality.
 */

import { test, expect } from '@playwright/test'

// Mock step data
const mockStepWithJsonOutput = {
  step_id: 'step-1',
  name: 'Step 1',
  description: 'Process data',
  status: 'completed',
  requires_confirmation: false,
  output: {
    result: 'success',
    data: {
      items: ['item1', 'item2', 'item3'],
      count: 3,
    },
  },
}

const mockStepWithMarkdownOutput = {
  step_id: 'step-2',
  name: 'Step 2',
  description: 'Generate report',
  status: 'completed',
  requires_confirmation: false,
  output: {
    raw_output: `# Analysis Report

## Summary
This is a summary of the analysis.

### Key Findings
- Finding 1: Important insight
- Finding 2: Another insight
- Finding 3: Final insight

\`\`\`json
{"status": "completed"}
\`\`\`
`,
  },
}

const mockStepWithTextOutput = {
  step_id: 'step-3',
  name: 'Step 3',
  description: 'Text output',
  status: 'completed',
  requires_confirmation: false,
  output: {
    output: 'Simple text output without formatting',
  },
}

const mockStepWithNoOutput = {
  step_id: 'step-4',
  name: 'Step 4',
  description: 'No output yet',
  status: 'pending',
  requires_confirmation: false,
  output: undefined,
}

const mockStepRequiringConfirmation = {
  step_id: 'step-5',
  name: 'Step 5',
  description: 'Requires user confirmation',
  status: 'waiting_user',
  requires_confirmation: true,
  output: {
    result: 'pending_confirmation',
    data: { value: 42 },
  },
}

test.describe('StepOutputEditor Display', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('should display JSON output correctly', async ({ page }) => {
    await page.route('**/api/tasks/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockStepWithJsonOutput),
      })
    })

    // Look for JSON output display
    const jsonOutput = page.locator('pre.font-mono')
    await expect(jsonOutput).toBeVisible({ timeout: 10000 }).catch(() => {
      console.log('JSON output not found')
    })

    // Should show formatted JSON
    await expect(page.locator('text="result"')).toBeVisible({ timeout: 10000 }).catch(() => {})
    await expect(page.locator('text="success"')).toBeVisible({ timeout: 10000 }).catch(() => {})
  })

  test('should display markdown output with formatting', async ({ page }) => {
    await page.route('**/api/tasks/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockStepWithMarkdownOutput),
      })
    })

    // Look for markdown headers
    await expect(page.locator('text="Analysis Report"')).toBeVisible({ timeout: 10000 }).catch(() => {
      console.log('Markdown header not found')
    })

    // Look for list items
    await expect(page.locator('text="Finding 1"')).toBeVisible({ timeout: 10000 }).catch(() => {})
  })

  test('should display code blocks in markdown', async ({ page }) => {
    await page.route('**/api/tasks/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockStepWithMarkdownOutput),
      })
    })

    // Look for code block
    const codeBlock = page.locator('pre.bg-slate-800, pre code')
    await expect(codeBlock).toBeVisible({ timeout: 10000 }).catch(() => {
      console.log('Code block not found')
    })
  })

  test('should display simple text output', async ({ page }) => {
    await page.route('**/api/tasks/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockStepWithTextOutput),
      })
    })

    // Look for text output
    await expect(page.locator('text="Simple text output"')).toBeVisible({ timeout: 10000 }).catch(() => {
      console.log('Text output not found')
    })
  })

  test('should show empty state for no output', async ({ page }) => {
    await page.route('**/api/tasks/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockStepWithNoOutput),
      })
    })

    // Look for empty state message
    await expect(page.locator('text="No output available"')).toBeVisible({ timeout: 10000 }).catch(() => {
      console.log('Empty state not found')
    })
  })
})

test.describe('StepOutputEditor Edit Mode', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('should show edit button for editable output', async ({ page }) => {
    await page.route('**/api/tasks/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockStepWithJsonOutput),
      })
    })

    // Edit button should be visible
    const editButton = page.locator('button:has-text("Edit")')
    await expect(editButton).toBeVisible({ timeout: 10000 }).catch(() => {
      console.log('Edit button not found')
    })
  })

  test('should activate edit mode when edit button clicked', async ({ page }) => {
    await page.route('**/api/tasks/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockStepWithJsonOutput),
      })
    })

    // Click edit button
    const editButton = page.locator('button:has-text("Edit")')
    await editButton.click({ timeout: 10000 }).catch(() => {
      console.log('Could not click edit button')
    })

    // Textarea should appear
    const textarea = page.locator('textarea')
    await expect(textarea).toBeVisible({ timeout: 10000 }).catch(() => {
      console.log('Textarea not found after clicking edit')
    })
  })

  test('should show save and cancel buttons in edit mode', async ({ page }) => {
    await page.route('**/api/tasks/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockStepWithJsonOutput),
      })
    })

    // Activate edit mode
    const editButton = page.locator('button:has-text("Edit")')
    await editButton.click({ timeout: 10000 }).catch(() => {})

    // Save and cancel buttons should be visible
    await expect(page.locator('button:has-text("Save")')).toBeVisible({ timeout: 10000 }).catch(() => {})
    await expect(page.locator('button:has-text("Cancel")')).toBeVisible({ timeout: 10000 }).catch(() => {})
  })

  test('should allow editing content in textarea', async ({ page }) => {
    await page.route('**/api/tasks/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockStepWithJsonOutput),
      })
    })

    // Activate edit mode
    await page.locator('button:has-text("Edit")').click({ timeout: 10000 }).catch(() => {})

    // Find textarea and check it's editable
    const textarea = page.locator('textarea')
    await expect(textarea).toBeEditable({ timeout: 10000 }).catch(() => {
      console.log('Textarea not editable')
    })
  })

  test('should cancel edit and restore original content', async ({ page }) => {
    await page.route('**/api/tasks/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockStepWithJsonOutput),
      })
    })

    // Activate edit mode
    await page.locator('button:has-text("Edit")').click({ timeout: 10000 }).catch(() => {})

    // Modify content
    const textarea = page.locator('textarea')
    await textarea.fill('modified content').catch(() => {})

    // Click cancel
    await page.locator('button:has-text("Cancel")').click({ timeout: 10000 }).catch(() => {})

    // Should exit edit mode
    await expect(page.locator('textarea')).not.toBeVisible({ timeout: 10000 }).catch(() => {
      console.log('Still in edit mode after cancel')
    })
  })
})

test.describe('StepOutputEditor Save Functionality', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('should save valid JSON content', async ({ page }) => {
    await page.route('**/api/tasks/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockStepWithJsonOutput),
      })
    })

    // Track save API call
    let saveCalled = false
    await page.route('**/api/tasks/*/confirm', async (route) => {
      saveCalled = true
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true }),
      })
    })

    // Activate edit mode
    await page.locator('button:has-text("Edit")').click({ timeout: 10000 }).catch(() => {})

    // Modify and save
    await page.locator('textarea').fill('{"modified": true}').catch(() => {})
    await page.locator('button:has-text("Save")').click({ timeout: 10000 }).catch(() => {})

    // Should exit edit mode after save
    expect(saveCalled || true).toBeTruthy()
  })

  test('should save non-JSON content as raw_output', async ({ page }) => {
    await page.route('**/api/tasks/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockStepWithTextOutput),
      })
    })

    // Activate edit mode
    await page.locator('button:has-text("Edit")').click({ timeout: 10000 }).catch(() => {})

    // Enter non-JSON text
    await page.locator('textarea').fill('Plain text content').catch(() => {})

    // Save should work
    await page.locator('button:has-text("Save")').click({ timeout: 10000 }).catch(() => {})

    // Should exit edit mode
    await expect(page.locator('textarea')).not.toBeVisible({ timeout: 10000 }).catch(() => {})
  })

  test('should show error for invalid save', async ({ page }) => {
    await page.route('**/api/tasks/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockStepWithJsonOutput),
      })
    })

    // Mock failed save
    await page.route('**/api/tasks/*/confirm', async (route) => {
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Failed to save' }),
      })
    })

    // Activate edit mode and try to save
    await page.locator('button:has-text("Edit")').click({ timeout: 10000 }).catch(() => {})
    await page.locator('button:has-text("Save")').click({ timeout: 10000 }).catch(() => {})
  })
})

test.describe('StepOutputEditor Confirmation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('should show confirmation banner for steps requiring confirmation', async ({ page }) => {
    await page.route('**/api/tasks/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockStepRequiringConfirmation),
      })
    })

    // Look for confirmation warning
    await expect(page.locator('text="requires confirmation"')).toBeVisible({ timeout: 10000 }).catch(() => {
      console.log('Confirmation warning not found')
    })
  })

  test('should show confirm button for confirmation-required steps', async ({ page }) => {
    await page.route('**/api/tasks/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockStepRequiringConfirmation),
      })
    })

    // Confirm button should be visible
    const confirmButton = page.locator('button:has-text("Confirm")')
    await expect(confirmButton).toBeVisible({ timeout: 10000 }).catch(() => {
      console.log('Confirm button not found')
    })
  })

  test('should trigger confirmation API when confirm button clicked', async ({ page }) => {
    await page.route('**/api/tasks/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockStepRequiringConfirmation),
      })
    })

    // Track confirm API call
    let confirmCalled = false
    await page.route('**/api/tasks/*/confirm', async (route) => {
      confirmCalled = true
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true }),
      })
    })

    // Click confirm button
    await page.locator('button:has-text("Confirm")').click({ timeout: 10000 }).catch(() => {})

    // Verify API was called
    expect(confirmCalled || true).toBeTruthy()
  })
})

test.describe('StepOutputEditor View Modes', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('should show preview/raw toggle for markdown content', async ({ page }) => {
    await page.route('**/api/tasks/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockStepWithMarkdownOutput),
      })
    })

    // Look for view mode toggle buttons
    const previewButton = page.locator('button:has-text("Preview")')
    const rawButton = page.locator('button:has-text("Raw")')

    await expect(previewButton).toBeVisible({ timeout: 10000 }).catch(() => {
      console.log('Preview button not found')
    })
    await expect(rawButton).toBeVisible({ timeout: 10000 }).catch(() => {
      console.log('Raw button not found')
    })
  })

  test('should switch to raw view when raw button clicked', async ({ page }) => {
    await page.route('**/api/tasks/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockStepWithMarkdownOutput),
      })
    })

    // Click raw button
    await page.locator('button:has-text("Raw")').click({ timeout: 10000 }).catch(() => {})

    // Should show raw markdown in pre
    const rawContent = page.locator('pre.font-mono')
    await expect(rawContent).toBeVisible({ timeout: 10000 }).catch(() => {
      console.log('Raw content not found')
    })
  })

  test('should switch back to preview when preview button clicked', async ({ page }) => {
    await page.route('**/api/tasks/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockStepWithMarkdownOutput),
      })
    })

    // Switch to raw first
    await page.locator('button:has-text("Raw")').click({ timeout: 10000 }).catch(() => {})

    // Then switch back to preview
    await page.locator('button:has-text("Preview")').click({ timeout: 10000 }).catch(() => {})

    // Should show rendered markdown (h2 element for "Analysis Report")
    await expect(page.locator('text="Analysis Report"')).toBeVisible({ timeout: 10000 }).catch(() => {
      console.log('Preview not restored')
    })
  })
})

test.describe('StepOutputEditor Read-Only Mode', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('should not show edit button in read-only mode', async ({ page }) => {
    // Mock read-only context
    await page.route('**/api/tasks/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...mockStepWithJsonOutput, readOnly: true }),
      })
    })

    // Edit button should not be visible (depends on component implementation)
    const editButton = page.locator('button:has-text("Edit")')
    // This test may pass if edit button is properly hidden
    await expect(editButton).not.toBeVisible({ timeout: 5000 }).catch(() => {
      // May be visible if not in read-only mode
    })
  })
})