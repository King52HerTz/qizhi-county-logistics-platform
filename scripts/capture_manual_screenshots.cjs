const { chromium } = require('playwright')
const path = require('path')

const output = process.argv[2]
if (!output) throw new Error('请提供截图输出目录')

async function settle(page) {
  await page.waitForLoadState('domcontentloaded')
  await page.waitForTimeout(2200)
}

async function shot(page, name) {
  await page.screenshot({
    path: path.join(output, name),
    fullPage: true,
    animations: 'disabled',
  })
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({
    viewport: { width: 1600, height: 1000 },
    deviceScaleFactor: 1,
    locale: 'zh-CN',
  })
  const page = await context.newPage()

  await page.goto('http://127.0.0.1/login')
  await settle(page)
  await shot(page, '01-login.png')

  await page.getByPlaceholder('请输入账号').fill('admin')
  await page.getByPlaceholder('请输入密码').fill('QizhiDemo2026!')
  await page.getByRole('button', { name: '安全登录' }).click()
  await page.waitForURL('**/overview')
  await settle(page)

  const guideClose = page.getByRole('button', { name: '退出操作引导' })
  if (await guideClose.count()) {
    await shot(page, '02-operation-guide.png')
    await guideClose.click()
    await page.waitForTimeout(500)
  }
  await shot(page, '03-overview.png')

  await page.goto('http://127.0.0.1/dispatch')
  await settle(page)
  await page.getByRole('button', { name: /重新生成方案/ }).first().click()
  await page.waitForTimeout(4500)
  await shot(page, '04-fixed-dispatch.png')

  await page.goto('http://127.0.0.1/events')
  await settle(page)
  await shot(page, '05-event-before.png')
  await page.getByRole('button', { name: /启动处置|重新计算方案/ }).first().click()
  await page.waitForTimeout(4500)
  await shot(page, '06-event-after.png')

  await page.goto('http://127.0.0.1/execution')
  await settle(page)
  await shot(page, '07-execution.png')

  await page.goto('http://127.0.0.1/settings/ai')
  await settle(page)
  await shot(page, '08-ai-settings.png')

  await page.goto('http://127.0.0.1/settings/map')
  await settle(page)
  await shot(page, '09-map-settings.png')

  const driverContext = await browser.newContext({
    viewport: { width: 1600, height: 1000 },
    deviceScaleFactor: 1,
    locale: 'zh-CN',
  })
  const driverPage = await driverContext.newPage()
  await driverPage.goto('http://127.0.0.1/login')
  await settle(driverPage)
  await driverPage.getByPlaceholder('请输入账号').fill('driver')
  await driverPage.getByPlaceholder('请输入密码').fill('DriverDemo2026!')
  await driverPage.getByRole('button', { name: '安全登录' }).click()
  await driverPage.waitForURL('**/overview')
  await settle(driverPage)
  const driverGuideClose = driverPage.getByRole('button', { name: '退出操作引导' })
  if (await driverGuideClose.count()) {
    await driverGuideClose.click()
    await driverPage.waitForTimeout(500)
  }
  await shot(driverPage, '10-driver-overview.png')
  await driverPage.goto('http://127.0.0.1/execution')
  await settle(driverPage)
  await shot(driverPage, '11-driver-execution.png')
  await driverContext.close()

  await browser.close()
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
