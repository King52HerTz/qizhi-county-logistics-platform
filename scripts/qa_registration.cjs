const { chromium } = require('playwright')
const path = require('path')

const baseUrl = 'http://127.0.0.1'
const screenshotDir = 'C:/Users/Administrator/.codex/visualizations/2026/07/23/019f8e73-7d46-7fb1-8a6f-6293dee4c391'
const username = `qa_${Date.now().toString().slice(-10)}`
const password = 'QizhiUser2026!'

async function main() {
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1 })

  await page.goto(`${baseUrl}/login`, { waitUntil: 'networkidle' })
  await page.screenshot({ path: path.join(screenshotDir, 'qizhi-login-with-register.png'), fullPage: true })
  await page.getByRole('link', { name: '创建运营账号' }).click()
  await page.waitForURL('**/register')
  await page.screenshot({ path: path.join(screenshotDir, 'qizhi-register-desktop.png'), fullPage: true })

  await page.getByLabel('姓名或称呼').fill('浏览器验证用户')
  await page.getByLabel('登录账号').fill(username)
  await page.getByLabel('登录密码').fill(password)
  await page.getByLabel('确认密码').fill(password)
  await page.getByText('我已阅读并同意平台账号与数据使用规范').click()
  await page.getByRole('button', { name: '创建账号并进入平台' }).click()
  await page.waitForURL('**/overview', { timeout: 15000 })
  await page.getByRole('heading', { name: '县域物流智能决策驾驶舱' }).waitFor()
  await page.screenshot({ path: path.join(screenshotDir, 'qizhi-registration-success.png'), fullPage: true })

  const apiLogin = await page.request.post(`${baseUrl}/api/v1/auth/login`, {
    data: { username, password },
  })
  if (!apiLogin.ok()) throw new Error(`Repeat login failed: ${apiLogin.status()}`)
  const loginBody = await apiLogin.json()
  if (loginBody.role !== 'driver') throw new Error(`Unexpected role: ${loginBody.role}`)

  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 })
  await mobile.goto(`${baseUrl}/register`, { waitUntil: 'networkidle' })
  await mobile.screenshot({ path: path.join(screenshotDir, 'qizhi-register-mobile.png'), fullPage: true })

  console.log(JSON.stringify({
    username,
    role: loginBody.role,
    desktopUrl: page.url(),
    mobileUrl: mobile.url(),
  }))
  await browser.close()
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
