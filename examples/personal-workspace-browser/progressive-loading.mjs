import { openWorkspacePage } from "./scenario-context.mjs";

// One Goal's lifecycle action must not send the rest of the workspace back to
// the loading lane. The directory entry is the cheap signal for "this Goal did
// not move", so only the touched Goal is re-read.
export const progressiveLoadingScenario = {
  id: "progressive-loading",
  async run({ browser, collectCoverage, url }) {
    const context = await openWorkspacePage(browser, url, {
      apiOptions: { progressiveWorkspace: true },
      collectCoverage,
    });
    const { api, coverageEntries, errors: pageErrors, page } = context;
    // Only the product's own reads are asserted: the development server may
    // refuse an asset it considers outside its root, which is a harness path
    // question rather than a client failure.
    const failedResponses = [];
    page.on("response", (response) => {
      if (response.status() >= 400 && response.url().includes("/api/")) {
        failedResponses.push(`${response.status()} ${response.url()}`);
      }
    });
    try {
      await page.waitForFunction(
        () => document.querySelectorAll(".personal-home-lane[aria-live]").length === 0,
        null,
        { timeout: 60_000 },
      );
      if (api.workspaceDirectoryRequests === 0) throw new Error("Progressive loading never read the workspace directory");
      const cardTitles = () => page.locator(".personal-home-lanes .personal-home-goal-card strong").allInnerTexts();
      const peers = (await cardTitles()).filter((title) => title !== "Product Release");
      if (peers.length === 0) throw new Error("Progressive loading rendered no peer Goal cards");
      const loadingCards = () => page.locator('.personal-home-goal-card[data-goal-state="loading"]').count();
      if (await loadingCards()) throw new Error("The workspace settled with a Goal still in its loading state");

      api.goalStatusRequests.length = 0;
      await page.getByRole("button", { name: "停止 Product Release", exact: true }).click();
      await page.waitForTimeout(3_000);

      const rereadPeers = [...new Set(api.goalStatusRequests)].filter((goalId) => goalId !== "product-release");
      if (rereadPeers.length) {
        throw new Error(`Pausing one Goal re-read its peers: ${JSON.stringify(rereadPeers)}`);
      }
      if (await loadingCards()) throw new Error("Pausing one Goal sent the workspace back to its loading lane");
      const afterStop = await cardTitles();
      for (const title of peers) {
        if (!afterStop.includes(title)) throw new Error(`Pausing one Goal dropped the peer card ${title}`);
      }
      const stoppedDirectory = page.locator(".personal-stopped-goals");
      if (!await stoppedDirectory.evaluate((node) => node.open)) {
        await stoppedDirectory.locator("summary").click();
      }

      api.goalStatusRequests.length = 0;
      await page.getByRole("button", { name: "恢复 Product Release", exact: true }).click();
      await page.getByText("确认执行", { exact: true }).waitFor({ state: "visible" });
      await page.locator('[data-action-review="review"]').filter({ hasText: "恢复自动调度前需要确认" }).waitFor({ state: "visible" });
      await page.getByRole("button", { name: "恢复 Goal", exact: true }).click();
      await page.waitForTimeout(3_000);

      const rereadPeersAfterResume = [...new Set(api.goalStatusRequests)]
        .filter((goalId) => goalId !== "product-release");
      if (rereadPeersAfterResume.length) {
        throw new Error(`Resuming one Goal re-read its peers: ${JSON.stringify(rereadPeersAfterResume)}`);
      }
      if (await loadingCards()) throw new Error("Resuming one Goal sent the workspace back to its loading lane");
      const resumed = await cardTitles();
      for (const title of peers) {
        if (!resumed.includes(title)) throw new Error(`Resuming one Goal dropped the peer card ${title}`);
      }
      if (!resumed.includes("Product Release")) throw new Error("The resumed Goal did not return to the workspace board");

      if (failedResponses.length) throw new Error(`Progressive reconciliation failed requests: ${failedResponses.join(" | ")}`);
      // The harness collects uncaught page errors and console errors; a
      // dev-server resource status is not a client-side exception.
      const scriptErrors = pageErrors.filter((message) => !message.startsWith("Failed to load resource"));
      if (scriptErrors.length) throw new Error(`Progressive reconciliation raised page errors: ${scriptErrors.join(" | ")}`);
      return {
        coverageEntries,
        note: "progressive loading reads the workspace directory once and then one Goal at a time; a single Goal's pause and resume re-read no peer, never re-enters the loading lane and keeps every peer card on the board",
      };
    } finally {
      coverageEntries.push(...await context.close());
    }
  },
};
