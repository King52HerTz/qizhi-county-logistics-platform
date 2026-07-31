const fs = require("node:fs");

const playwrightPath = process.env.PLAYWRIGHT_CORE_PATH;
if (!playwrightPath) {
  throw new Error("PLAYWRIGHT_CORE_PATH is required");
}

const { chromium } = require(playwrightPath);

const baseUrl = process.env.APP_BASE_URL || "http://localhost";
const username = process.env.APP_USERNAME || "admin";
const password = process.env.APP_PASSWORD;
const browserPath =
  process.env.BROWSER_PATH ||
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const cdpUrl = process.env.CDP_URL;
const outputPath = process.env.OUTPUT_PATH;

if (!password) {
  throw new Error("APP_PASSWORD is required");
}

async function main() {
  const browser = cdpUrl
    ? await chromium.connectOverCDP(cdpUrl)
    : await chromium.launch({
        headless: true,
        executablePath: browserPath,
      });
  try {
    const page = await browser.newPage();
    const loginResponse = await page.request.post(
      `${baseUrl}/api/v1/auth/login`,
      { data: { username, password } },
    );
    if (!loginResponse.ok()) {
      throw new Error(`Login failed: ${loginResponse.status()}`);
    }
    const auth = await loginResponse.json();
    await page.goto(`${baseUrl}/login`);
    await page.evaluate((session) => {
      localStorage.setItem("qizhi_access_token", session.access_token);
      localStorage.setItem("qizhi_session_role", session.role);
      localStorage.setItem(
        "qizhi_session_user",
        session.display_name || session.username,
      );
    }, auth);
    await page.goto(`${baseUrl}/master-data/spatial`, {
      waitUntil: "networkidle",
      timeout: 60_000,
    });
    await page.waitForFunction(() => window.AMap, null, { timeout: 30_000 });

    const nodes = await page.evaluate(async () => {
      const token = localStorage.getItem("qizhi_access_token");
      const response = await fetch("/api/v1/master-data/nodes?limit=100", {
        headers: { Authorization: `Bearer ${token}` },
      });
      return (await response.json()).items;
    });

    const results = await page.evaluate(async (masterNodes) => {
      await new Promise((resolve) =>
        window.AMap.plugin(["AMap.Geocoder", "AMap.PlaceSearch"], resolve),
      );
      const geocoder = new window.AMap.Geocoder({
        city: "衡阳市",
        citylimit: false,
      });
      const placeSearch = new window.AMap.PlaceSearch({
        city: "祁东县",
        citylimit: true,
        pageSize: 10,
      });
      const locate = (query) =>
        new Promise((resolve) => {
          geocoder.getLocation(query, (status, result) => {
            resolve({
              query,
              status,
              info: result?.info,
              count: result?.count,
              geocodes: (result?.geocodes || []).map((item) => ({
                formatted_address: item.formattedAddress,
                province: item.addressComponent?.province,
                city: item.addressComponent?.city,
                district: item.addressComponent?.district,
                township: item.addressComponent?.township,
                neighborhood: item.addressComponent?.neighborhood?.name,
                building: item.addressComponent?.building?.name,
                level: item.level,
                longitude: item.location?.lng,
                latitude: item.location?.lat,
              })),
            });
          });
        });
      const reverse = (position) =>
        new Promise((resolve) => {
          geocoder.getAddress(position, (status, result) => {
            const component = result?.regeocode?.addressComponent;
            resolve({
              status,
              info: result?.info,
              formatted_address: result?.regeocode?.formattedAddress,
              province: component?.province,
              city: component?.city,
              district: component?.district,
              township: component?.township,
              towncode: component?.towncode,
            });
          });
        });
      const searchPlace = (keywords) =>
        new Promise((resolve) => {
          placeSearch.search(keywords, (status, result) => {
            resolve({
              keywords,
              status,
              info: result?.info,
              pois: (result?.poiList?.pois || []).map((item) => ({
                id: item.id,
                name: item.name,
                type: item.type,
                address: item.address,
                district: item.adname,
                longitude: item.location?.lng,
                latitude: item.location?.lat,
              })),
            });
          });
        });
      const audited = [];
      for (const node of masterNodes) {
        const query = `湖南省衡阳市祁东县${node.address || node.name}`;
        const geocode = await locate(query);
        const first = geocode.geocodes[0];
        const placeKeywords =
          node.id === "D-01"
            ? "衡缘物流园"
            : node.name.replace(
                /(加工点|集散点|产业园|服务站|县域共配中心)$/,
                "",
              );
        audited.push({
          node,
          geocode,
          reverse_geocode: first
            ? await reverse([first.longitude, first.latitude])
            : null,
          place_search: await searchPlace(placeKeywords),
        });
      }
      return audited;
    }, nodes);

    const payload = `${JSON.stringify(results, null, 2)}\n`;
    if (outputPath) fs.writeFileSync(outputPath, payload, "utf8");
    process.stdout.write(payload);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
