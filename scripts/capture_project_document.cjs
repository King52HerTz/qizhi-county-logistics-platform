const { chromium } = require('playwright')
const path = require('path')

const baseUrl = 'http://127.0.0.1'
const outputDir = 'E:/wuliu_project/docs/assets/project-document'

async function settle(page) {
  await page.waitForLoadState('domcontentloaded')
  await page.waitForTimeout(1800)
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 })
  page.on('dialog', dialog => dialog.accept())
  await page.addInitScript(() => localStorage.setItem('qizhi_operation_guide_v1', 'completed'))

  await page.goto(`${baseUrl}/login`, { waitUntil: 'networkidle' })
  await page.screenshot({ path: path.join(outputDir, '01-login.png'), fullPage: true })
  await page.getByRole('link', { name: '创建运营账号' }).click()
  await page.waitForURL('**/register')
  await page.screenshot({ path: path.join(outputDir, '02-register.png'), fullPage: true })

  await page.goto(`${baseUrl}/login`, { waitUntil: 'networkidle' })
  await page.getByLabel('账号').fill('admin')
  await page.getByPlaceholder('请输入密码').fill('QizhiDemo2026!')
  await page.getByRole('button', { name: '安全登录' }).click()
  await page.waitForURL('**/overview')

  const routes = [
    ['03-overview.png', '/overview'],
    ['04-dispatch.png', '/dispatch'],
    ['05-events.png', '/events'],
    ['06-execution.png', '/execution'],
    ['07-experiments.png', '/experiments'],
    ['08-master-data.png', '/master-data/orders'],
    ['09-settings-ai.png', '/settings/ai'],
  ]
  for (const [filename, route] of routes) {
    await page.goto(`${baseUrl}${route}`, { waitUntil: 'networkidle' })
    await settle(page)
    await page.screenshot({ path: path.join(outputDir, filename), fullPage: true })
  }

  console.log(JSON.stringify({ screenshots: routes.length + 2, outputDir }))
  await browser.close()
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
