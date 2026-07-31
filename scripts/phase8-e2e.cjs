const { chromium } = require('playwright')

const edgePath = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
const evidenceRoot = 'C:/Users/Administrator/.codex/visualizations/2026/07/23/019f8e73-7d46-7fb1-8a6f-6293dee4c391'

async function run() {
  const browser = await chromium.launch({ headless: true, executablePath: edgePath })
  const errors = []
  const context = await browser.newContext({
    viewport: { width: 1600, height: 1000 },
    acceptDownloads: true,
  })
  const page = await context.newPage()
  page.on('console', message => {
    if (message.type() === 'error') errors.push(`console: ${message.text()}`)
  })
  page.on('pageerror', error => errors.push(`pageerror: ${error.message}`))

  await page.goto('http://127.0.0.1/settings/users', { waitUntil: 'networkidle' })
  const redirectWorked = page.url().includes('/login?redirect=')
  await page.locator('input[autocomplete="username"]').fill('admin')
  await page.locator('input[autocomplete="current-password"]').fill('QizhiDemo2026!')
  await page.getByRole('button', { name: '安全登录' }).click()
  await page.waitForURL('**/settings/users')
  await page.getByRole('heading', { name: '用户与权限' }).waitFor()

  await page.getByRole('button', { name: '新建用户' }).click()
  await page.getByRole('heading', { name: '新建用户' }).waitFor()
  await page.locator('.user-drawer input[placeholder="请输入姓名"]').fill('界面验收预览')
  await page.locator('.user-drawer input[placeholder*="dispatcher01"]').fill('preview_qa')
  const drawerPath = `${evidenceRoot}/phase8-users-drawer-final.png`
  await page.screenshot({ path: drawerPath, fullPage: true })
  await page.locator('.user-drawer header button').click()

  const tabsHorizontal = await page.locator('.settings-tabs button').evaluateAll(elements => {
    const positions = elements.map(element => Math.round(element.getBoundingClientRect().top))
    return new Set(positions).size === 1
  })
  const usersOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  )
  const usersPath = `${evidenceRoot}/phase8-users-page-final.png`
  await page.screenshot({ path: usersPath, fullPage: true })

  await page.goto('http://127.0.0.1/settings/audit', { waitUntil: 'networkidle' })
  await page.getByRole('heading', { name: '审计日志' }).waitFor()
  await page.locator('button.audit-row').first().click()
  await page.getByRole('heading', { name: '审计详情' }).waitFor()
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出记录' }).click()
  const download = await downloadPromise
  const auditOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  )
  const auditPath = `${evidenceRoot}/phase8-audit-page-final.png`
  await page.screenshot({ path: auditPath, fullPage: true })

  const mobileErrors = []
  const mobileContext = await browser.newContext({ viewport: { width: 390, height: 844 } })
  const mobile = await mobileContext.newPage()
  mobile.on('console', message => {
    if (message.type() === 'error') mobileErrors.push(`console: ${message.text()}`)
  })
  mobile.on('pageerror', error => mobileErrors.push(`pageerror: ${error.message}`))
  await mobile.goto('http://127.0.0.1/login', { waitUntil: 'networkidle' })
  const mobileOverflow = await mobile.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  )
  const mobilePath = `${evidenceRoot}/phase8-login-mobile-final.png`
  await mobile.screenshot({ path: mobilePath, fullPage: true })

  console.log(JSON.stringify({
    redirectWorked,
    tabsHorizontal,
    usersOverflow,
    auditOverflow,
    download: download.suggestedFilename(),
    errors,
    mobileOverflow,
    mobileErrors,
    paths: { drawerPath, usersPath, auditPath, mobilePath },
  }, null, 2))

  await mobileContext.close()
  await context.close()
  await browser.close()
}

run().catch(error => {
  console.error(error)
  process.exit(1)
})
