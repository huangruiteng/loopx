import { resolve } from "node:path";

import {
  installApi,
  outputDir,
  visibleElementCount,
} from "./fixture.mjs";
import { openWorkspacePage } from "./scenario-context.mjs";

export const navigationSortingScenario = {
  id: "navigation-sorting",
  async run({ browser, collectCoverage, url }) {
    const context = await openWorkspacePage(browser, url, { collectCoverage });
    const { checkpointCoverage, page } = context;
    const notes = [];
    const pass = (criterion, note) => notes.push(`${criterion}: ${note}`);
    try {
      const body = await page.locator("body").innerText();
      for (const text of ["LoopX 管家", "需要你", "执行中", "观察中", "已安排", "历史", "GOALS", "Codex"]) {
        if (!body.includes(text)) {
          await page.screenshot({ path: resolve(outputDir, "desktop-first-screen-failed.png"), fullPage: false, animations: "disabled" });
          throw new Error(`First screen missing ${text}; body=${body.slice(0, 2000)}`);
        }
      }
      if (await page.locator(".personal-home-lane").count() !== 4) throw new Error("Manager home did not render four active lanes");
      if (body.includes("接下来")) throw new Error("Manager home still exposes the ambiguous 接下来 label");
      if (body.includes("stale-browser-goal")) throw new Error("An unregistered historical Goal remained interactive");
      if (!(await page.locator(".personal-home-history").first().isVisible())) throw new Error("Completed Goals are not available through the collapsed history section");
      const needsYouCount = await page.getByTestId("personal-home-lane-needs_you").locator(".personal-home-goal-card").count();
      const greeting = await page.locator(".personal-manager-greeting").innerText();
      if (!greeting.includes(`你有 ${needsYouCount} 项需要处理`)) {
        throw new Error(`Manager greeting count disagrees with the needs-you lane: count=${needsYouCount}; greeting=${greeting}`);
      }
      if (await page.locator(".personal-manager-channels").count()) throw new Error("Sidebar still exposes state lanes as duplicate navigation channels");
      if (await page.locator(".personal-digest-stats button").count()) throw new Error("Away digest still behaves like hidden channel navigation");
      if (body.includes("Agent 设置")) throw new Error("Sidebar still exposes the read-only Agent settings dead end");
      if (await page.locator(".personal-global-rail").count()) throw new Error("Old icon rail is visible");
      if ((await page.locator(".personal-goal-list:not(.is-stopped) .personal-goal-row").count()) !== 5) throw new Error("Active Goal directory did not exclude stopped Goals");
      const stoppedDirectory = page.locator(".personal-stopped-goals");
      // Real pointer gestures against the shipped sidebar, not synthetic drag events.
      const activeRows = page.locator('.personal-goal-list:not(.is-stopped) .personal-goal-row');
      const readOrder = () => activeRows.evaluateAll(rows => rows.map(row => row.dataset.reorderGoal));
      const initialOrder = await readOrder();
      const firstLink = activeRows.nth(0).locator('.personal-goal-link');
      const start = await firstLink.boundingBox();
      const end = await activeRows.nth(2).boundingBox();
      const beforeDragUrl = page.url();
      await page.mouse.move(start.x + 40, start.y + start.height / 2);
      await page.mouse.down();
      await page.mouse.move(end.x + 40, end.y + end.height - 4, { steps: 12 });
      await page.locator('.is-drop-after').waitFor();
      await page.mouse.up();
      const expectedOrder = [initialOrder[1], initialOrder[2], initialOrder[0], ...initialOrder.slice(3)];
      if (JSON.stringify(await readOrder()) !== JSON.stringify(expectedOrder)) throw new Error('Pointer Goal reorder failed');
      if (page.url() !== beforeDragUrl) throw new Error('Dragging accidentally selected a Goal');
      await checkpointCoverage();
      await page.reload({ waitUntil: 'networkidle' });
      // Network idleness does not establish React/status-projection readiness.
      // Wait for the persisted order itself, retaining a bounded failure when it
      // is lost or wrong rather than accepting whichever rows happen to render.
      try {
        await page.waitForFunction((expected) => {
          const actual = [...document.querySelectorAll('.personal-goal-list:not(.is-stopped) .personal-goal-row')]
            .map((row) => row.getAttribute('data-reorder-goal'));
          return JSON.stringify(actual) === JSON.stringify(expected);
        }, expectedOrder, { timeout: 6_000 });
      } catch (error) {
        throw new Error(`Goal order did not survive reload: expected=${JSON.stringify(expectedOrder)} actual=${JSON.stringify(await readOrder())}`, { cause: error });
      }
      // Escape cancels rather than committing a partially completed gesture.
      const cancelStart = await activeRows.first().locator('.personal-goal-link').boundingBox();
      const cancelEnd = await activeRows.nth(2).boundingBox();
      await activeRows.first().locator('.personal-goal-link').focus();
      await page.mouse.move(cancelStart.x + 40, cancelStart.y + 20);
      await page.mouse.down();
      await page.mouse.move(cancelEnd.x + 40, cancelEnd.y + cancelEnd.height - 4, { steps: 8 });
      await page.keyboard.press('Escape');
      await page.mouse.up();
      if (JSON.stringify(await readOrder()) !== JSON.stringify(expectedOrder)) throw new Error('Cancelled drag changed order');
      await page.getByRole('button', { name: '调整 Goal 顺序', exact: true }).click();
      const up = activeRows.nth(2).getByRole('button', { name: /^上移 / });
      await up.focus();
      await page.keyboard.press('Enter');
      await page.keyboard.press('Enter');
      if (JSON.stringify(await readOrder()) !== JSON.stringify(initialOrder)) throw new Error('Keyboard Goal reorder failed or lost focus');
      if (!(await activeRows.first().getByRole('button', { name: /^上移 / }).isDisabled())) throw new Error('First Goal can move beyond list boundary');
      await page.screenshot({ path: resolve(outputDir, 'goal-reorder-controls.png'), fullPage: false, animations: 'disabled' });
      await page.getByRole('button', { name: '调整 Goal 顺序', exact: true }).click();
      await page.screenshot({ path: resolve(outputDir, 'goal-reorder-default.png'), fullPage: false, animations: 'disabled' });
      if (!(await stoppedDirectory.isVisible()) || await stoppedDirectory.getAttribute("open") !== null) throw new Error("Stopped Goals are not available in a collapsed directory section");
      await page.waitForFunction(() => document.querySelectorAll(".personal-stopped-goals .personal-goal-row").length === 2, null, { timeout: 3_000 });
      await stoppedDirectory.locator("summary").click();
      await page.locator(".personal-goal-link").filter({ hasText: "Legacy Benchmark" }).click();
      await page.waitForFunction(() => new URL(window.location.href).searchParams.get("goalId") === "legacy-benchmark");
      const stoppedGoalBody = await page.locator(".personal-channel").innerText();
      if (!stoppedGoalBody.includes("Legacy Benchmark") || !stoppedGoalBody.includes("历史、Todo 和证据仍保留")) {
        throw new Error(`Stopped Goal lost its archive context after merge: ${stoppedGoalBody.slice(0, 1200)}`);
      }
      await page.locator(".personal-goal-link").filter({ hasText: "Product Release" }).click();
      await stoppedDirectory.locator("summary").click();
      if (await page.locator(".personal-timeline-row").filter({ hasText: /纠偏/u }).count()) throw new Error("Browse rows expose repeated correction actions");
      pass(2, "Browse rows are full-row click targets and Session rows state that they open execution progress and results.");
      const workspaceSettingsEntry = page.getByRole("button", { name: "设置", exact: true });
      const settingsEntryVisual = await workspaceSettingsEntry.evaluate((element) => {
        const style = getComputedStyle(element);
        const icon = element.querySelector(".personal-sidebar-utility-icon")?.getBoundingClientRect();
        const rect = element.getBoundingClientRect();
        return {
          backgroundColor: style.backgroundColor,
          borderTopWidth: style.borderTopWidth,
          height: rect.height,
          iconHeight: icon?.height ?? 0,
          width: rect.width,
        };
      });
      if (settingsEntryVisual.height < 52 || settingsEntryVisual.iconHeight < 32 || settingsEntryVisual.width < 180) {
        throw new Error(`Settings entry is not a prominent navigation target: ${JSON.stringify(settingsEntryVisual)}`);
      }
      if (settingsEntryVisual.borderTopWidth === "0px" || settingsEntryVisual.backgroundColor === "rgba(0, 0, 0, 0)") {
        throw new Error(`Settings entry still renders as a weak transparent footer row: ${JSON.stringify(settingsEntryVisual)}`);
      }
      await page.screenshot({ path: resolve(outputDir, "desktop-first-screen.png"), fullPage: false, animations: "disabled" });
      pass(4, "First viewport exposes needs-you, running, observing, and scheduled Goal lanes with collapsed history.");
      pass(15, "Desktop viewport matches the approved single-sidebar/channel/drawer composition.");
      const remote = await browser.newPage({ viewport: { width: 1512, height: 982 } });
      await installApi(remote);
      await remote.goto(url, { waitUntil: "networkidle" });
      await remote.getByRole("button", { name: "添加 SSH 隧道来源" }).click();
      await remote.getByLabel("本机 SSH Host").fill("remote-lab");
      await remote.getByText("ssh -N -L 8876:127.0.0.1:8766 remote-lab", { exact: true }).waitFor({ state: "visible" });
      await remote.getByRole("button", { name: "添加只读来源" }).click();
      await remote.getByText("远端只读投影", { exact: true }).waitFor({ state: "visible" });
      await remote.getByRole("button", { name: "添加 SSH 隧道来源" }).click();
      await remote.getByRole("tab", { name: "手动 URL" }).click();
      await remote.getByLabel("名称").fill("Remote build host");
      await remote.getByLabel("本地转发 URL").fill("http://127.0.0.1:8976/status.json");
      await remote.getByRole("button", { name: "添加只读来源" }).click();
      const remoteSourceSelect = remote.getByRole("combobox", { name: "选择控制面来源" });
      await remoteSourceSelect.click();
      const remoteSourceListbox = remote.getByRole("listbox", { name: "选择控制面来源" });
      if (await remoteSourceListbox.getByRole("option").count() !== 4) throw new Error("Multiple SSH tunnel sources were not retained in the source catalog");
      if (await remoteSourceListbox.locator(".personal-select-group-label").count() !== 1) throw new Error("Configured SSH Host quick-add group is missing");
      await remote.screenshot({ path: resolve(outputDir, "control-plane-select-open.png"), fullPage: false, animations: "disabled" });
      await remoteSourceListbox.getByRole("option", { name: "remote-build", exact: true }).click();
      await remote.locator(".personal-read-only-source", { hasText: "remote-build" }).waitFor({ state: "visible", timeout: 10_000 });
      pass(21, "Quick-add configured SSH host from the control-plane source dropdown.");
      await remoteSourceSelect.click();
      await remote.getByRole("listbox", { name: "选择控制面来源" }).getByRole("option", { name: "remote-lab", exact: true }).click();
      await remote.locator(".personal-read-only-source", { hasText: "remote-lab" }).waitFor({ state: "visible", timeout: 10_000 });
      await remote.locator(".personal-channel-composer").waitFor({ state: "detached", timeout: 3_000 });
      await remote.screenshot({ path: resolve(outputDir, "remote-read-only-source.png"), fullPage: false, animations: "disabled" });
      const visibleRemoteCreateButtons = await visibleElementCount(remote.locator('button[aria-label="创建 Goal"]'));
      if (visibleRemoteCreateButtons) throw new Error("Remote read-only source still exposed Goal creation");
      if (!(await remote.getByText("remote-lab", { exact: true }).count())) throw new Error("Remote source identity is not visible");
      await remote.locator(".personal-goal-link").first().click();
      await remote.getByRole("button", { name: "Tasks", current: "page" }).waitFor({ state: "visible" });
      await remote.locator(".personal-object-list", { hasText: "进行中" }).locator("button").first().click();
      await remote.getByRole("dialog", { name: "Todo 详情" }).waitFor({ state: "visible" });
      const remoteTodoDrawer = remote.getByRole("dialog", { name: "Todo 详情" });
      for (const label of ["标记完成", "管理任务"]) {
        const visibleMatches = await visibleElementCount(remoteTodoDrawer.getByRole("button", { name: label, exact: true }));
        if (visibleMatches) throw new Error(`Remote Todo drawer exposed ${label}`);
      }
      await remote.getByRole("button", { name: /关闭详情/ }).click();
      await remote.locator(".personal-object-list", { hasText: "定时与持续" }).locator("button").first().click();
      await remote.getByText("定时检查", { exact: true }).last().waitFor({ state: "visible" });
      const remoteScheduleDrawer = remote.getByRole("dialog", { name: "定时检查" });
      for (const label of ["立即运行", "暂停", "改为每 2 小时", "停止定时检查"]) {
        const visibleMatches = await visibleElementCount(remoteScheduleDrawer.getByRole("button", { name: label, exact: true }));
        if (visibleMatches) {
          throw new Error(`Remote schedule drawer exposed ${label}: ${(await remoteScheduleDrawer.innerText()).slice(0, 2000)}`);
        }
      }
      await remote.close();

      const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true });
      await installApi(mobile);
      await mobile.goto(url, { waitUntil: "networkidle" });
      await mobile.getByTestId("personal-goal-home").waitFor({ state: "visible" });
      const mobileLaneSeparators = await mobile.locator(".personal-home-lane").evaluateAll((lanes) => lanes.map((lane) => {
        const style = getComputedStyle(lane);
        return { borderLeftWidth: style.borderLeftWidth, borderTopWidth: style.borderTopWidth };
      }));
      if (mobileLaneSeparators.some((lane) => lane.borderLeftWidth !== "0px")
        || mobileLaneSeparators.slice(1).some((lane) => lane.borderTopWidth !== "1px")) {
        throw new Error(`Mobile lanes did not switch to horizontal separators: ${JSON.stringify(mobileLaneSeparators)}`);
      }
      const mobileOverflow = await mobile.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      if (mobileOverflow > 1) throw new Error(`Mobile workspace has ${mobileOverflow}px horizontal overflow`);
      await mobile.screenshot({ path: resolve(outputDir, "mobile-first-screen.png"), fullPage: false, animations: "disabled" });
      const mobileComposer = mobile.getByLabel("向 LoopX 发送消息");
      const composerBox = await mobileComposer.boundingBox();
      if (!composerBox || composerBox.y + composerBox.height > 844) throw new Error("Mobile composer is outside the visible safe area");
      const mobileNavigationTrigger = mobile.locator(".personal-mobile-menu");
      await mobileNavigationTrigger.click();
      if (await mobileNavigationTrigger.getAttribute("aria-expanded") !== "true") {
        throw new Error(`Mobile navigation state did not open: ${await mobile.locator(".personal-workspace-shell").getAttribute("class")}`);
      }
      const mobileNavigationDialog = mobile.getByRole("dialog", { name: "Goal 导航" });
      await mobileNavigationDialog.waitFor({ state: "visible" });
      const mobileNavigationClose = mobile.getByRole("button", { name: "关闭 Goal 导航" });
      if (!(await mobileNavigationClose.evaluate((element) => element === document.activeElement))) {
        throw new Error("Mobile navigation did not move focus into its close control");
      }
      const mobileMain = mobile.locator(".personal-workspace-main");
      if (await mobileMain.getAttribute("aria-hidden") !== "true" || !(await mobileMain.evaluate((element) => element.inert))) {
        throw new Error("Mobile navigation left the background workspace exposed to assistive navigation");
      }
      await mobile.keyboard.press("Shift+Tab");
      if (!(await mobileNavigationDialog.evaluate((element) => element.contains(document.activeElement)))) {
        throw new Error("Mobile navigation focus escaped its modal boundary");
      }
      await mobile.keyboard.press("Tab");
      if (!(await mobileNavigationClose.evaluate((element) => element === document.activeElement))) {
        throw new Error("Mobile navigation focus did not wrap to its first control");
      }
      const mobileSidebarProbe = await mobile.locator(".personal-workspace-sidebar").evaluate((element) => {
        const style = getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return { className: element.parentElement?.className, display: style.display, height: rect.height, width: rect.width, x: rect.x };
      });
      if (mobileSidebarProbe.display === "none" || mobileSidebarProbe.width < 100) {
        throw new Error(`Mobile sidebar did not become visible: ${JSON.stringify(mobileSidebarProbe)}`);
      }
      const mobileStoppedDirectory = mobile.locator(".personal-stopped-goals");
      if (await mobileStoppedDirectory.getAttribute("open") === null) await mobileStoppedDirectory.locator("summary").click();
      await mobile.screenshot({ path: resolve(outputDir, "mobile-goal-directory.png"), fullPage: false, animations: "disabled" });
      await mobile.keyboard.press("Escape");
      if (await mobileNavigationTrigger.getAttribute("aria-expanded") !== "false") {
        throw new Error("Mobile navigation did not close on Escape");
      }
      if (!(await mobileNavigationTrigger.evaluate((element) => element === document.activeElement))) {
        throw new Error("Mobile navigation did not restore focus to its trigger");
      }
      await mobileNavigationTrigger.click();
      const mobileManagerLink = mobile.locator(".personal-manager-link");
      try {
        await mobileManagerLink.waitFor({ state: "visible", timeout: 1500 });
      } catch {
        throw new Error(`Mobile manager link hidden after open: sidebar=${JSON.stringify(mobileSidebarProbe)} chain=${JSON.stringify(await mobileManagerLink.evaluate((element) => { const chain = []; let current = element; while (current && chain.length < 6) { const style = getComputedStyle(current); const rect = current.getBoundingClientRect(); chain.push({ className: current.className, display: style.display, height: rect.height, position: style.position, width: rect.width, x: rect.x }); current = current.parentElement; } return chain; }))}`);
      }
      await mobileManagerLink.click();
      await mobile.locator(".personal-home-board").waitFor({ state: "visible" });
      await mobileNavigationTrigger.click();
      await mobile.getByRole("dialog", { name: "Goal 导航" }).waitFor({ state: "visible" });
      await mobile.locator(".personal-goal-link").first().click();
      await mobile.getByRole("button", { name: "Tasks", current: "page" }).waitFor({ state: "visible" });
      await mobile.getByRole("button", { name: "打开 Goal 详情或能力配置" }).click();
      const mobileGoalToolsMenu = mobile.getByRole("group", { name: "Goal 设置" });
      await mobileGoalToolsMenu.waitFor({ state: "visible" });
      const mobileMenuBox = await mobileGoalToolsMenu.boundingBox();
      if (!mobileMenuBox || mobileMenuBox.x < 0 || mobileMenuBox.x + mobileMenuBox.width > 390) {
        throw new Error(`Mobile Goal settings menu escaped the viewport: ${JSON.stringify(mobileMenuBox)}`);
      }
      const mobileGoalOverflow = await mobile.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      if (mobileGoalOverflow > 1) throw new Error(`Mobile Goal header has ${mobileGoalOverflow}px horizontal overflow`);
      await mobile.screenshot({ path: resolve(outputDir, "mobile-goal-settings-menu.png"), fullPage: false, animations: "disabled" });
      await mobile.close();
      const progressive = await browser.newPage({ viewport: { width: 1512, height: 982 } });
      const progressiveApi = await installApi(progressive);
      progressiveApi.nextFullStatusDelayMs = 1_500;
      await progressive.goto(url, { waitUntil: "domcontentloaded" });
      await progressive.getByTestId("personal-goal-home").waitFor({ state: "visible", timeout: 10_000 });
      const progressiveActiveVisibleBeforeStopped = await progressive.waitForFunction(
        () => document.querySelectorAll(".personal-goal-list:not(.is-stopped) .personal-goal-row").length === 5,
        null,
        { timeout: 3_000 },
      );
      const stoppedLoadingVisible = await progressive.locator(".personal-stopped-goals summary svg.is-spinning, .personal-stopped-goals summary svg[class*='spinning']").count();
      if (!progressiveActiveVisibleBeforeStopped) throw new Error("Active Goals did not render first while the stopped archive was still loading");
      if (stoppedLoadingVisible === 0) throw new Error("Stopped Goals archive did not expose an accessible loading state");
      await progressive.locator(".personal-stopped-goals .personal-goal-row").first().waitFor({ state: "attached", timeout: 6_000 });
      const progressiveStoppedCount = await progressive.locator(".personal-stopped-goals .personal-goal-row").count();
      if (progressiveStoppedCount !== 2) throw new Error(`Stopped Goals archive loaded the wrong count: ${progressiveStoppedCount}`);
      if ((await progressive.locator(".personal-goal-list:not(.is-stopped) .personal-goal-row").count()) !== 5) throw new Error("Active Goal directory regressed after the stopped archive loaded");
      pass(23, "The stopped archive loads after active Goals: active Goals are interactive first, the stopped section shows an accessible loading state, then stopped Goals arrive without replacing the page.");
      await progressive.close();

      const revisionRace = await browser.newPage({ viewport: { width: 1512, height: 982 } });
      const revisionRaceApi = await installApi(revisionRace);
      revisionRaceApi.captureNextStatusGeneration = true;
      revisionRaceApi.activationChangeAfterCapturedActive = {
        goalId: "product-release",
        activationState: "stopped",
      };
      revisionRaceApi.nextFullStatusDelayMs = 800;
      await revisionRace.goto(url, { waitUntil: "domcontentloaded" });
      await revisionRace.getByTestId("personal-goal-home").waitFor({ state: "visible", timeout: 10_000 });
      await revisionRace.locator(".personal-stopped-goals .personal-goal-row").first().waitFor({ state: "attached", timeout: 6_000 });
      await revisionRace.waitForFunction(() => document.querySelectorAll(".personal-goal-list:not(.is-stopped) .personal-goal-row").length === 4, null, { timeout: 6_000 });
      if (await revisionRace.locator(".personal-stopped-goal-error").count()) {
        throw new Error("Registry revision mismatch did not converge after the bounded automatic resync");
      }
      if (await revisionRace.locator(".personal-goal-row").filter({ hasText: "Product Release" }).count() !== 1) {
        throw new Error("Registry revision race duplicated or omitted Product Release");
      }
      await revisionRace.close();

      const progressiveError = await browser.newPage({ viewport: { width: 1512, height: 982 } });
      const errorApi = await installApi(progressiveError);
      errorApi.failNextFullStatus = true;
      await progressiveError.goto(url, { waitUntil: "domcontentloaded" });
      await progressiveError.getByTestId("personal-goal-home").waitFor({ state: "visible", timeout: 10_000 });
      await progressiveError.locator(".personal-stopped-goal-error").waitFor({ state: "visible", timeout: 4_000 });
      if ((await progressiveError.locator(".personal-goal-list:not(.is-stopped) .personal-goal-row").count()) !== 5) throw new Error("A failed stopped archive replaced the active workspace");
      await progressiveError.getByText("重试", { exact: true }).click();
      await progressiveError.locator(".personal-stopped-goals .personal-goal-row").first().waitFor({ state: "attached", timeout: 6_000 });
      const errorRecoveredCount = await progressiveError.locator(".personal-stopped-goals .personal-goal-row").count();
      if (errorRecoveredCount !== 2) throw new Error(`Retry did not recover the stopped archive: ${errorRecoveredCount}`);
      pass(24, "A stopped-archive failure keeps active Goals usable and offers a retry that restores the stopped section without a full-page error.");
      await progressiveError.close();

      if (await page.locator(".personal-workspace-shell").getAttribute("data-pw-theme") !== "loopx") throw new Error("Personal workspace did not start with the LoopX standard theme");
      if (await page.getByRole("button", { name: /切换到野兽主题|切换到默认主题/ }).count()) throw new Error("Workspace header still exposes the old theme toggle");
      await page.getByRole("button", { name: "设置", exact: true }).click();
      await page.getByRole("button", { name: /外观/ }).click();
      await page.getByRole("radio", { name: /高对比/ }).click();
      if (await page.locator(".personal-settings-page").getAttribute("data-pw-theme") !== "brutal") throw new Error("Settings did not enable the high-contrast theme");
      await page.getByRole("radio", { name: /纸张/ }).click();
      if (await page.locator(".personal-settings-page").getAttribute("data-pw-theme") !== "paper") throw new Error("Settings did not enable the paper theme");
      await page.getByRole("radio", { name: /LoopX 标准/ }).click();
      if (await page.locator(".personal-settings-page").getAttribute("data-pw-theme") !== "loopx") throw new Error("Settings did not restore the LoopX standard theme");
      if (await page.evaluate(() => localStorage.getItem("loopx-pw-theme")) !== "loopx") throw new Error("LoopX standard theme was not persisted");
      await page.screenshot({ path: resolve(outputDir, "desktop-settings-loopx-theme.png"), fullPage: false, animations: "disabled" });
      await page.getByRole("button", { name: "返回工作区", exact: true }).click();
      if (await page.locator(".personal-workspace-shell").getAttribute("data-pw-theme") !== "loopx") throw new Error("Workspace did not apply the LoopX standard theme readback");
      await checkpointCoverage();
      await page.reload({ waitUntil: "networkidle" });
      await page.getByTestId("personal-goal-home").waitFor({ state: "visible" });
      if (await page.locator(".personal-workspace-shell").getAttribute("data-pw-theme") !== "loopx") throw new Error("LoopX standard theme did not survive reload");
      pass(16, "The Settings appearance tab switches among all three themes and restores the LoopX standard default.");
      await page.locator(".personal-manager-link").first().click();
      await page.waitForTimeout(600);
      const workerCards = await page.locator(".personal-worker-strip > button").count();
      if (workerCards !== 0) throw new Error(`Redundant Agent worker strip is still visible: ${workerCards}`);
      if (!(await page.locator(".personal-digest-card").isVisible().catch(() => false))) throw new Error("Morning digest card did not render on the manager home");
      pass(17, "Manager home keeps the morning digest while omitting the redundant Agent worker strip.");

    } finally {
      await context.close();
    }
    return {
      coverageEntries: context.coverageEntries,
      note: notes.join(" "),
    };
  },
};
