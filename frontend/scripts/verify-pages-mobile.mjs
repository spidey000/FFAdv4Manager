// End-to-end smoke test against the live GitHub Pages deployment.
// Run with: npm i --no-save --no-package-lock playwright && npx playwright install chromium
//          node scripts/verify-pages-mobile.mjs
import { chromium } from 'playwright'
import fs from 'node:fs'

const url = process.env.PAGES_URL || 'https://spidey000.github.io/Three_slicer_responsive/'
const widths = [320, 360, 390, 430]
const output = 'pages-mobile-screenshots'
fs.mkdirSync(output, { recursive: true })

const browser = await chromium.launch({
  headless: true,
  args: [
    '--no-sandbox',
    '--enable-webgl',
    '--use-gl=angle',
    '--use-angle=swiftshader',
    '--enable-unsafe-swiftshader',
    '--disable-dev-shm-usage',
  ],
})

async function checkWidth(width) {
  const page = await browser.newPage({
    viewport: { width, height: 844 },
    deviceScaleFactor: 1,
    isMobile: true,
    hasTouch: true,
  })
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 90000 })
    await page.waitForFunction(() => {
      const find = node => {
        if (node.querySelector?.('.empty-hint')) return node.querySelector('.empty-hint')
        for (const element of node.querySelectorAll?.('*') || []) {
          if (element.shadowRoot) {
            const found = find(element.shadowRoot)
            if (found) return found
          }
        }
        return null
      }
      return !!find(document)
    }, null, { timeout: 90000 })
    await page.waitForTimeout(1000)

    const geometry = await page.evaluate(() => {
      const find = node => {
        const matching = node.querySelector?.('.empty-hint')
        if (matching) return matching
        for (const element of node.querySelectorAll?.('*') || []) {
          if (element.shadowRoot) {
            const result = find(element.shadowRoot)
            if (result) return result
          }
        }
        return null
      }
      const card = find(document)
      const frame = card.getBoundingClientRect()
      const canvas = card.closest('.vp-canvas')?.getBoundingClientRect()
      const button = card.querySelector('button')?.getBoundingClientRect()
      return {
        viewport: window.innerWidth,
        card: { left:frame.left, right:frame.right, top:frame.top, bottom:frame.bottom, width:frame.width },
        canvas: canvas ? {left:canvas.left, right:canvas.right} : null,
        button: button ? {left:button.left, right:button.right} : null,
        visibility: getComputedStyle(card).visibility,
      }
    })
    await page.screenshot({ path: `${output}/mobile-${width}.png`, fullPage: true })
    const english = await page.evaluate(() => {
      const find = node => {
        const matching = node.querySelector?.('.empty-hint')
        if (matching) return matching
        for (const element of node.querySelectorAll?.('*') || []) {
          if (element.shadowRoot) {
            const result = find(element.shadowRoot)
            if (result) return result
          }
        }
        return null
      }
      const card = find(document)
      return {
        lang: document.documentElement.lang,
        title: card?.querySelector('.eh-title')?.textContent?.trim(),
        button: card?.querySelector('.eh-btn')?.textContent?.trim(),
      }
    })
    if (english.lang !== 'en' || english.title !== 'Your next project starts here' || english.button !== 'Open 3D model') {
      throw new Error(`English UI regression at ${width}px: ${JSON.stringify(english)}`)
    }
    if (width === 390) {
      await page.locator('.nav-setting').click()
      await page.waitForTimeout(150)
      const modal = page.locator('.settings-drawer')
      const modalContent = await modal.textContent()
      if (!modalContent.includes('Slicing settings') || !modalContent.includes('Print configuration')) {
        throw new Error('Mobile settings panel is not in English')
      }
      await page.screenshot({ path: `${output}/settings-mobile-${width}.png`, fullPage: true })

      // The first loaded material must be Artillery PLA Basic, regardless of
      // the first vendor-recommended filament in the upstream AD4 catalog.
      await page.waitForFunction(() =>
        document.querySelector('#ad4-material-select')?.value === 'Artillery PLA Basic @Flashforge AD4',
        null, { timeout: 30000 })
      if (await page.locator('#ad4-material-select').inputValue() !== 'Artillery PLA Basic @Flashforge AD4') {
        throw new Error('Default Artillery PLA material is not selected')
      }

      // Save process + material snapshots from the two dropdowns, then reload.
      await page.waitForFunction(() => document.querySelector('#ad4-process-select')?.options.length > 2)
      await page.locator('#ad4-process-select').selectOption('__save_new_process_profile__')
      await page.locator('#new-profile-name').fill('E2E custom process')
      await page.getByRole('button', { name: 'Save profile' }).click()
      if (await page.locator('#ad4-process-select').inputValue() !== 'E2E custom process') {
        throw new Error('Saved process was not selected')
      }
      await page.locator('#ad4-material-select').selectOption('__save_new_filament_profile__')
      await page.locator('#new-profile-name').fill('E2E custom filament')
      await page.getByRole('button', { name: 'Save profile' }).click()
      if (await page.locator('#ad4-material-select').inputValue() !== 'E2E custom filament') {
        throw new Error('Saved material was not selected')
      }
      if (!await page.locator('#ad4-material-select option').filter({ hasText: 'Artillery PLA Basic' }).count()) {
        throw new Error('Artillery PLA Basic preset is missing')
      }
      await page.reload({ waitUntil: 'domcontentloaded' })
      await page.locator('.nav-setting').click()
      await page.waitForFunction(() => document.querySelector('#ad4-process-select')?.options.length > 2)
      const savedProcess = await page.locator('#ad4-process-select option').filter({ hasText: 'E2E custom process' }).count()
      const savedMaterial = await page.locator('#ad4-material-select option').filter({ hasText: 'E2E custom filament' }).count()
      if (!savedProcess || !savedMaterial) throw new Error('Custom profiles did not survive a reload')
      await page.screenshot({ path: `${output}/saved-profiles-mobile-${width}.png`, fullPage: true })
      await page.locator('.close-drawer').click()
      // The AD4 status control must open the real responsive manager, even when
      // GitHub Pages correctly has no backend to execute physical commands.
      await page.locator('button.ad4-printer-state').click()
      const manager = page.locator('.pm-overlay')
      await manager.waitFor({ state: 'visible', timeout: 10000 })
      if (!(await manager.textContent()).includes('Gestión de impresora')) {
        throw new Error('AD4 printer manager not rendered')
      }
      const mobileManager = await page.evaluate(() => {
        const panel = document.querySelector('.pm-window')
        const frame = panel?.getBoundingClientRect()
        return frame && { left: frame.left, right: frame.right, width: innerWidth }
      })
      if (!mobileManager || mobileManager.left < -2 || mobileManager.right > width + 2) {
        throw new Error('Printer manager clipped at 390px: ' + JSON.stringify(mobileManager))
      }
      await page.screenshot({ path: output + '/printer-manager-mobile-' + width + '.png', fullPage: true })
      await page.locator('.pm-back').click()

    }

    const tolerance = 2
    const bounds = [geometry.card, geometry.button].filter(Boolean)
    for (const rect of bounds) {
      if (rect.left < -tolerance || rect.right > geometry.viewport + tolerance) {
        throw new Error(`Clipped at ${width}px: ${JSON.stringify(geometry)}`)
      }
    }
    if (geometry.card.width < 200 || geometry.visibility !== 'visible') {
      throw new Error(`Unexpected card dimensions at ${width}px: ${JSON.stringify(geometry)}`)
    }
    console.log(`PASS viewport=${width}px card=[${Math.round(geometry.card.left)},${Math.round(geometry.card.right)}] button=[${Math.round(geometry.button?.left)},${Math.round(geometry.button?.right)}]`)
  } catch (error) {
    await page.screenshot({ path: `${output}/mobile-${width}-error.png`, fullPage: true }).catch(() => {})
    throw error
  } finally {
    await page.close()
  }
}

try {
  for (const width of widths) await checkWidth(width)
  console.log(`PASS: all ${widths.length} mobile viewport sizes, live URL: ${url}`)
} finally {
  await browser.close()
}
