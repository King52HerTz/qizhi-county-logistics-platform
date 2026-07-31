const { chromium } = require('playwright')
const { pathToFileURL } = require('url')
const path = require('path')

async function main() {
  const [htmlPath, outputDir] = process.argv.slice(2)
  if (!htmlPath || !outputDir) throw new Error('需要 HTML 路径和截图目录')
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  await page.goto(pathToFileURL(path.resolve(htmlPath)).href)
  await page.waitForLoadState('load')
  const report = await page.evaluate(() => ({
    title: document.title,
    sections: document.querySelectorAll('main section').length,
    images: [...document.images].map((image) => ({
      complete: image.complete,
      width: image.naturalWidth,
      alt: image.alt,
    })),
    brokenLinks: [...document.querySelectorAll('nav a')]
      .map((link) => link.getAttribute('href'))
      .filter((href) => !href || !document.querySelector(href)),
    horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
  }))
  await page.screenshot({ path: path.join(outputDir, 'manual-html-top.png'), fullPage: false })
  await page.locator('#dispatch').scrollIntoViewIfNeeded()
  await page.screenshot({ path: path.join(outputDir, 'manual-html-dispatch.png'), fullPage: false })
  await page.locator('#faq').scrollIntoViewIfNeeded()
  await page.screenshot({ path: path.join(outputDir, 'manual-html-faq.png'), fullPage: false })
  process.stdout.write(JSON.stringify(report, null, 2))
  await browser.close()
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
