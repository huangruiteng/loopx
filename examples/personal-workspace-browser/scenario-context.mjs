import { installApi } from "./fixture.mjs";

export async function openWorkspacePage(
  browser,
  url,
  {
    apiOptions,
    beforeGoto,
    collectCoverage = false,
    gotoWaitUntil = "networkidle",
    viewport = { width: 1512, height: 982 },
    isMobile = false,
  } = {},
) {
  const page = await browser.newPage({ viewport, isMobile });
  const errors = [];
  const coverageEntries = [];
  let coverageRunning = false;
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  if (collectCoverage) {
    await page.coverage.startJSCoverage({ resetOnNavigation: false });
    coverageRunning = true;
  }
  const api = await installApi(page, apiOptions);
  await beforeGoto?.(api, page);
  await page.goto(url, { waitUntil: gotoWaitUntil });
  try {
    await page.getByTestId("personal-goal-home").waitFor({ state: "visible", timeout: 15_000 });
  } catch (error) {
    throw new Error(
      `${error.message}; url=${page.url()}; errors=${errors.join(" | ")}; body=${(await page.locator("body").innerText()).slice(0, 1000)}`,
    );
  }

  async function checkpointCoverage() {
    if (!coverageRunning) return;
    coverageEntries.push(...await page.coverage.stopJSCoverage());
    await page.coverage.startJSCoverage({ resetOnNavigation: false });
  }

  async function close() {
    if (coverageRunning) {
      coverageEntries.push(...await page.coverage.stopJSCoverage());
      coverageRunning = false;
    }
    await page.close();
    return coverageEntries;
  }

  return { api, checkpointCoverage, close, coverageEntries, errors, page };
}
