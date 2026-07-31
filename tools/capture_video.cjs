const { chromium } = require("C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.pnpm/playwright@1.61.1/node_modules/playwright");
const path = require("path");
const fs = require("fs");

(async () => {
  const source = path.resolve(process.argv[2]);
  const outDir = path.resolve(process.argv[3]);
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    executablePath: "C:/Users/Administrator/AppData/Local/Google/Chrome/Application/chrome.exe",
    args: ["--allow-file-access-from-files"],
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const videoUrl = "file:///" + source.replace(/\\/g, "/").replace(/ /g, "%20");
  await page.goto(videoUrl, {waitUntil: "domcontentloaded", timeout: 15000});
  await page.addStyleTag({content:"html,body{margin:0;background:#111;height:100%}video{width:100vw!important;height:100vh!important;object-fit:contain}"});
  const metadata = await page.evaluate(() => new Promise((resolve, reject) => {
    const v = document.querySelector("video");
    const timer = setTimeout(() => reject(new Error("metadata timeout")), 15000);
    v.addEventListener("loadedmetadata", () => resolve({duration:v.duration,width:v.videoWidth,height:v.videoHeight}));
    v.addEventListener("error", () => reject(new Error(v.error ? v.error.message : "video load failed")));
    if (v.readyState >= 1) {
      clearTimeout(timer);
      resolve({duration:v.duration,width:v.videoWidth,height:v.videoHeight});
    }
  }));
  console.log(JSON.stringify(metadata));
  const count = 16;
  for (let i = 0; i < count; i++) {
    const t = Math.max(0, metadata.duration * i / (count - 1) - 0.05);
    await page.evaluate((time) => new Promise((resolve) => {
      const v = document.querySelector("video");
      const done = () => { v.removeEventListener("seeked", done); resolve(); };
      v.addEventListener("seeked", done);
      v.currentTime = time;
    }), t);
    await page.screenshot({path:path.join(outDir, `frame-${String(i+1).padStart(2,"0")}-${t.toFixed(1)}s.png`)});
  }
  await browser.close();
})().catch((err) => { console.error(err); process.exit(1); });
