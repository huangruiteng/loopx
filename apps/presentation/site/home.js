const setupPrompts = {
  en: `Connect the current project to LoopX: https://github.com/huangruiteng/loopx

Do not clone LoopX. Follow the README Quick Start to use the no-clone installer and \`loopx doctor\`, then reuse or \`loopx connect/bootstrap\` the current project state.

After setup, first report the project connection status, current user gate, top agent todo, next safe action, and available commands.

Then I will use \`/loopx <complex task>\` to begin real work.
When you receive \`/loopx <goal text>\`, first provide a concise ordered plan, then write it as P0/P1/P2 todos so I can see what needs to be done, what is blocked by a gate, and what the next safe action is.`,
  zh: `把当前项目接入 LoopX: https://github.com/huangruiteng/loopx

不要 clone LoopX；按 README Quick Start 使用 no-clone installer、
\`loopx doctor\`，复用或 \`loopx connect/bootstrap\` 当前项目状态。

接入后先汇报：项目连接状态、当前 user gate、top agent todo、
next safe action，以及可用命令。

然后我会直接用 \`/loopx <复杂任务>\` 开始真实工作。
收到 \`/loopx <goal text>\` 后，先给出简洁有序计划，再把它写成
P0/P1/P2 todos，让我能看到当前要做什么、什么被 gate 卡住、
下一步安全动作是什么。`,
};

const zh = {
  "nav.product": "产品",
  "nav.workflow": "工作方式",
  "nav.learn": "学习",
  "nav.showcases": "案例",
  "nav.docs": "文档",
  "nav.github": "GitHub",
  "hero.eyebrow": "开放 · 有状态 · Provider-neutral",
  "hero.title": "Agent <span class=\"hero-phrase\"><span class=\"hero-wave\" data-hero-wave=\"progress\">持续推进</span>。</span><br />判断始终<span class=\"hero-phrase\"><span class=\"hero-wave\" data-hero-wave=\"judgment\">由你掌握</span>。</span>",
  "hero.body": "面向长程 Agent 的开放、有状态、Provider-neutral 控制面，把权限状态、Gate、Todo、Quota、Evidence、恢复与交接组织在同一闭环中。",
  "hero.copyPrompt": "复制 Agent 安装指令",
  "hero.promptCopied": "已复制，请粘贴给当前 Agent",
  "hero.copyFailed": "复制失败，请打开安装指南",
  "hero.copyPromptAria": "复制 LoopX 设置指令并粘贴给当前 Agent",
  "hero.demo": "查看演示",
  "agentSetup.label": "一条指令交给当前 Agent",
  "agentSetup.detect": "识别当前 Host",
  "agentSetup.preserve": "复用已有状态",
  "agentSetup.activate": "激活运行闭环",
  "agentSetup.description": "粘贴给 Codex、Claude Code、OpenCode、Cursor 或其他具备 Shell 能力的 Agent。它会遵循官方指南，并选择匹配当前 Host 的路径。",
  "agentSetup.manual": "手动安装 ↓",
  "agentSetup.guide": "阅读设置指南 ↗",
  "agentSetup.pointsAria": "设置指令要求 Agent 完成的事项",
  "visual.activeGoal": "当前目标",
  "visual.goalText": "交付可审查的结果",
  "visual.onTrack": "进展正常",
  "visual.lanesMoving": "2 条执行线路推进中",
  "visual.researcher": "研究 Agent",
  "visual.researching": "收集与分析",
  "visual.running": "运行中",
  "visual.writer": "写作 Agent",
  "visual.writing": "撰写内容",
  "visual.waitingForYou": "等待你的判断",
  "visual.humanGate": "人工 Gate",
  "visual.reviewApprove": "审查与批准",
  "visual.waiting": "等待中",
  "visual.evidenceWritten": "Evidence 已写回",
  "visual.artifacts": "已记录 128 项产物",
  "visual.artifactTypes": "日志、文档与输出",
  "visual.completed": "已完成",
  "proof.gates": "显式 Gate",
  "proof.gatesBody": "只在高价值判断点请求人工介入。",
  "proof.sideLanes": "安全侧路",
  "proof.sideLanesBody": "不绕过权限，独立工作仍可继续。",
  "proof.outcomes": "可审查结果",
  "proof.outcomesBody": "每次状态流转都为下一轮留下证据。",
  "product.eyebrow": "一个有状态控制面",
  "product.title": "让长程工作始终受控。",
  "product.body": "Agent runtime 负责执行；LoopX 治理跨运行延续的控制状态，让工程、研究、discovery 与运营 Loop 能持续推进。",
  "flow.goal": "长期目标",
  "flow.goalBody": "一个稳定方向",
  "flow.gate": "权限 Gate",
  "flow.gateBody": "一个具体决策",
  "flow.lanes": "Agent 执行线路",
  "flow.lanesBody": "有边界地继续",
  "flow.evidence": "Evidence",
  "flow.evidenceBody": "经过验证的结果",
  "flow.next": "下一轮运行",
  "flow.nextBody": "可恢复地推进",
  "capabilities.eyebrow": "跨 Provider、运行时与宿主",
  "capabilities.title": "一套有状态控制面，连接不同 Agent Runtime。",
  "capabilities.body": "Codex App、Codex CLI、Claude Code、OpenCode 与自定义 Runner 可以共享同一套有状态目标生命周期，同时让每个 Agent 保持明确边界。",
  "capabilities.state": "持久状态",
  "capabilities.stateBody": "目标、用户决策、Todo、Claim、Quota、运行历史与交接不会随会话结束而丢失。",
  "capabilities.runtime": "跨运行时",
  "capabilities.runtimeBody": "更换执行器或宿主时，无需从聊天记录重建长期目标。",
  "capabilities.gate": "Gate-aware",
  "capabilities.gateBody": "P0 等待决策时保持可见，独立的 P1、P2 线路可以安全继续。",
  "capabilities.evidence": "结果驱动",
  "capabilities.evidenceBody": "每轮运行都把验证、归属、审查和交接证据写入下一轮闭环。",
  "showcase.eyebrow": "来自真实闭环的证据",
  "showcase.title": "跨越 200+ 小时，依然清晰可读。",
  "showcase.body": "一条公开贡献序列与一条经过脱敏的 owner-run showcase，保留了多轮 Agent 推进中的交付、决策、证据分支与恢复过程。",
  "showcase.elapsed": "200+ 小时自然时长",
  "showcase.publicSafe": "公开安全证据",
  "showcase.shellTitle": "~/loopx/evidence — 精选回放",
  "showcase.tabsAria": "真实闭环终端示例",
  "showcase.pause": "暂停",
  "showcase.pauseAria": "暂停终端回放",
  "showcase.resume": "继续",
  "showcase.resumeAria": "继续终端回放",
  "showcase.replay": "重播",
  "showcase.replayAria": "重新播放终端示例",
  "showcase.curated": "基于公开证据的精选回放",
  "showcase.state.active": "进行中",
  "showcase.state.running": "运行中",
  "showcase.state.waiting": "等待中",
  "showcase.state.ready": "已就绪",
  "showcase.state.written": "已写回",
  "showcase.state.safe": "安全",
  "showcase.state.matched": "已匹配",
  "showcase.state.visible": "可见",
  "showcase.issue.tab": "问题修复",
  "showcase.issue.title": "PR 交付与可复用修复知识共同演进。",
  "showcase.issue.session": "公开轨迹 01 · 开源问题修复",
  "showcase.issue.command": "$ loopx status --goal-id issue-fix",
  "showcase.issue.goal": "交付聚焦修复，并保留可复用知识。",
  "showcase.issue.p0": "聚焦式 PR 交付 · 有边界的改动与验证",
  "showcase.issue.gate": "审查权限 · 批准聚焦改动",
  "showcase.issue.p1": "仓库知识与终端恢复保持可用",
  "showcase.issue.evidence": "合并 / 开放结果连接到下一轮可复用发现",
  "showcase.issue.next": "先审查聚焦改动，再继续能力沉淀线路。",
  "showcase.ml.tab": "自动化 ML",
  "showcase.ml.title": "证据分支保持可见，直到晋级或停止。",
  "showcase.ml.session": "脱敏 owner-run showcase 02 · 自动化 ML 实验",
  "showcase.ml.boundaryLabel": "经过脱敏的 owner-run showcase",
  "showcase.ml.command": "$ loopx status --goal-id auto-ml",
  "showcase.ml.baseline": "匹配候选项与评估契约已锁定。",
  "showcase.ml.positive": "正向",
  "showcase.ml.negative": "负向",
  "showcase.ml.invalid": "无效谱系",
  "showcase.ml.replicate": "运行中复现",
  "showcase.ml.p1": "证据持续积累，同时保持复现容量有界",
  "showcase.ml.evidence": "负向结果和无效谱系持续可追溯",
  "showcase.ml.gate": "运行中复现完成后，决定晋级或停止",
  "showcase.ml.next": "比较复现证据，再记录最终决策。",
  "showcase.viewFull": "查看完整证据",
  "showcase.boundary": "这里的时长是项目自然时长。Auto ML 材料是经过脱敏的 owner-run showcase，不代表生产结果、公司或雇主背书，也不是可独立复现的证据。",
  "dialog.eyebrow": "原始公开安全轨迹",
  "dialog.reset": "重置",
  "dialog.openOriginal": "在新标签页打开原图",
  "dialog.zoomOut": "缩小",
  "dialog.zoomIn": "放大",
  "dialog.close": "关闭证据查看器",
  "dialog.viewport": "拖动以平移证据轨迹",
  "quickstart.eyebrow": "手动备用方案",
  "quickstart.title": "更习惯终端？可以手动安装 LoopX。",
  "quickstart.description": "当你使用的 Agent 无法执行 Shell 命令时使用这条路径。同一官方安装器会为受支持的 Host 注册轻量命令入口。",
  "quickstart.checkDoctor": "✓ CLI 健康检查完成",
  "quickstart.checkState": "✓ 项目状态可以读取",
  "quickstart.checkActivation": "→ 按照 onboarding packet 完成 Host 激活",
  "quickstart.link": "阅读快速开始 →",
  "quickstart.inspect": "查看安装脚本 ↗",
  "footer.tagline": "让闭环持续运转，让判断始终属于人。",
  "footer.frontstage": "Frontstage",
  "learn.eyebrow": "开发者手册",
  "learn.title": "选择你的 LoopX 学习路径。",
  "learn.body": "为想要理解控制面、接入真实项目或在正确 ownership 边界上贡献的开发者准备的系统性双语协议指南。",
  "learn.openBook": "打开开发者手册 →",
  "learn.foundations": "理解控制面",
  "learn.foundationsBody": "从会话与目标出发，逐步建立对持久状态、权限、治理回合与恢复的完整认知。",
  "learn.readFoundations": "从基础开始 ↗",
  "learn.onboarding": "接入已有项目",
  "learn.onboardingBody": "让 Agent 建立 Goal、身份、Host 与 Git 边界，然后验证结果。",
  "learn.readOnboarding": "跟随项目接入指南 ↗",
  "learn.contribute": "贡献 LoopX",
  "learn.contributeBody": "从协议追踪到源码归属，选择正确的贡献面，验证后提交聚焦的 PR。",
  "learn.readContribute": "打开贡献地图 ↗",
};

const textTargets = document.querySelectorAll("[data-i18n]");
const htmlTargets = document.querySelectorAll("[data-i18n-html]");
const ariaTargets = document.querySelectorAll("[data-i18n-aria]");
const developerBookTargets = document.querySelectorAll("[data-devbook-path]");
textTargets.forEach((target) => { target.dataset.english = target.textContent; });
htmlTargets.forEach((target) => { target.dataset.englishHtml = target.innerHTML; });
ariaTargets.forEach((target) => { target.dataset.englishAria = target.getAttribute("aria-label") ?? ""; });

function applyLanguage(nextLanguage, updateUrl = false) {
  const language = nextLanguage === "zh" ? "zh" : "en";
  document.body.dataset.language = language;
  document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  textTargets.forEach((target) => {
    target.textContent = language === "zh" ? (zh[target.dataset.i18n] ?? target.dataset.english) : target.dataset.english;
  });
  htmlTargets.forEach((target) => {
    target.innerHTML = language === "zh" ? (zh[target.dataset.i18nHtml] ?? target.dataset.englishHtml) : target.dataset.englishHtml;
  });
  ariaTargets.forEach((target) => {
    target.setAttribute("aria-label", language === "zh" ? (zh[target.dataset.i18nAria] ?? target.dataset.englishAria) : target.dataset.englishAria);
  });
  developerBookTargets.forEach((target) => {
    const developerBookBase = target.dataset.devbookBase;
    const localePrefix = language === "zh" ? "" : "/en";
    const chapterPath = target.dataset.devbookPath === "/" ? "" : target.dataset.devbookPath;
    target.setAttribute("href", `${developerBookBase}${localePrefix}${chapterPath}/`);
  });
  prepareHeroWaves();
  document.querySelectorAll("[data-language-toggle]").forEach((toggle) => {
    toggle.textContent = language === "zh" ? "EN" : "中文";
    toggle.setAttribute("aria-label", language === "zh" ? "Switch to English" : "切换为中文");
  });
  const menu = document.querySelector(".menu-button");
  if (menu && menu.getAttribute("aria-expanded") !== "true") {
    menu.setAttribute("aria-label", language === "zh" ? "打开导航" : "Open navigation");
  }
  document.title = language === "zh" ? "LoopX — 让长程目标持续推进" : "LoopX — Keep the loop moving";
  document.querySelector('meta[name="description"]')?.setAttribute("content", language === "zh"
    ? "LoopX 是面向长程 Agent 的开放、有状态、Provider-neutral 控制面。"
    : "LoopX is the open, provider-neutral, stateful control plane for long-running agents across sessions, runtimes, and hosts.");
  if (updateUrl) {
    const url = new URL(window.location.href);
    if (language === "zh") url.searchParams.set("lang", "zh");
    else url.searchParams.delete("lang");
    window.history.replaceState({}, "", url);
  }
}

function prepareHeroWaves() {
  document.querySelectorAll("[data-hero-wave]").forEach((wave) => {
    const phrase = wave.textContent ?? "";
    wave.setAttribute("aria-label", phrase);
    wave.textContent = "";
    [...phrase].forEach((character, index) => {
      const span = document.createElement("span");
      span.setAttribute("aria-hidden", "true");
      span.style.setProperty("--char-delay", `${index * 55}ms`);
      span.textContent = character === " " ? "\u00a0" : character;
      wave.append(span);
    });
  });
}

const requestedLanguage = new URLSearchParams(window.location.search).get("lang");
const initialLanguage = requestedLanguage === "zh" ? "zh" : "en";
applyLanguage(initialLanguage);

document.querySelectorAll("[data-language-toggle]").forEach((toggle) => {
  toggle.addEventListener("click", () => {
    applyLanguage(document.body.dataset.language === "zh" ? "en" : "zh", true);
    refreshTerminalControls();
    if (toggle.classList.contains("mobile-language-toggle")) {
      const navigation = document.querySelector(".mobile-nav");
      const menu = document.querySelector(".menu-button");
      if (navigation) navigation.hidden = true;
      if (menu) {
        menu.setAttribute("aria-expanded", "false");
        menu.setAttribute("aria-label", document.body.dataset.language === "zh" ? "打开导航" : "Open navigation");
      }
    }
  });
});

const menuButton = document.querySelector(".menu-button");
const mobileNav = document.querySelector(".mobile-nav");

if (menuButton && mobileNav) {
  menuButton.addEventListener("click", () => {
    const nextOpen = menuButton.getAttribute("aria-expanded") !== "true";
    menuButton.setAttribute("aria-expanded", String(nextOpen));
    const chinese = document.body.dataset.language === "zh";
    menuButton.setAttribute("aria-label", nextOpen ? (chinese ? "关闭导航" : "Close navigation") : (chinese ? "打开导航" : "Open navigation"));
    mobileNav.hidden = !nextOpen;
  });

  mobileNav.addEventListener("click", (event) => {
    if (event.target instanceof HTMLAnchorElement) {
      menuButton.setAttribute("aria-expanded", "false");
      menuButton.setAttribute("aria-label", document.body.dataset.language === "zh" ? "打开导航" : "Open navigation");
      mobileNav.hidden = true;
    }
  });
}

function localizedText(target) {
  const key = target?.dataset.i18n;
  if (!target || !key) return "";
  return document.body.dataset.language === "zh" ? (zh[key] ?? target.dataset.english ?? "") : (target.dataset.english ?? "");
}

async function writeClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return;
  } catch {
    const activeElement = document.activeElement;
    const fallback = document.createElement("textarea");
    fallback.value = text;
    fallback.setAttribute("readonly", "");
    fallback.setAttribute("aria-hidden", "true");
    fallback.tabIndex = -1;
    fallback.style.position = "fixed";
    fallback.style.inset = "0 auto auto -9999px";
    document.body.append(fallback);
    let copied = false;
    try {
      fallback.focus({ preventScroll: true });
      fallback.select();
      fallback.setSelectionRange(0, fallback.value.length);
      copied = typeof document.execCommand === "function" && document.execCommand("copy");
    } finally {
      fallback.remove();
      if (activeElement instanceof HTMLElement) activeElement.focus({ preventScroll: true });
    }
    if (!copied) throw new Error("clipboard unavailable");
  }
}

const copyButtons = document.querySelectorAll("[data-copy-key]");
copyButtons.forEach((copyButton) => {
  if (!(copyButton instanceof HTMLButtonElement)) return;
  copyButton.addEventListener("click", async () => {
    const language = document.body.dataset.language === "zh" ? "zh" : "en";
    const copyKey = copyButton.dataset.copyKey;
    const copyText = copyKey === "agentSetup" ? setupPrompts[language] : "";
    const label = copyButton.querySelector("[data-copy-feedback]");
    try {
      await writeClipboard(copyText);
      if (label) label.textContent = language === "zh" ? zh["hero.promptCopied"] : "Copied — paste into your agent";
    } catch {
      if (label) label.textContent = language === "zh" ? zh["hero.copyFailed"] : "Copy failed — open the setup guide";
    }
    window.setTimeout(() => {
      if (label) label.textContent = localizedText(label);
    }, 2600);
  });
});

const terminalShowcase = document.querySelector("[data-terminal-showcase]");
const terminalTabs = [...document.querySelectorAll("[data-terminal-tab]")];
const terminalPanels = [...document.querySelectorAll("[data-terminal-panel]")];
const terminalMotionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
const terminalControlLabels = {
  en: {
    running: { label: "Pause", aria: "Pause terminal replay" },
    paused: { label: "Resume", aria: "Resume terminal replay" },
    complete: { label: "Replay", aria: "Replay terminal example" },
  },
  zh: {
    running: { label: zh["showcase.pause"], aria: zh["showcase.pauseAria"] },
    paused: { label: zh["showcase.resume"], aria: zh["showcase.resumeAria"] },
    complete: { label: zh["showcase.replay"], aria: zh["showcase.replayAria"] },
  },
};

function activeTerminalPanel() {
  return terminalPanels.find((panel) => !panel.hidden);
}

function refreshTerminalControls() {
  const language = document.body.dataset.language === "zh" ? "zh" : "en";
  terminalPanels.forEach((panel) => {
    const state = panel.dataset.playbackState || "running";
    const copy = terminalControlLabels[language][state] || terminalControlLabels[language].running;
    const control = panel.querySelector("[data-terminal-control]");
    const label = panel.querySelector("[data-terminal-control-label]");
    if (control) control.setAttribute("aria-label", copy.aria);
    if (label) label.textContent = copy.label;
  });
}

function setTerminalPlaybackState(panel, state) {
  panel.dataset.playbackState = state;
  panel.classList.toggle("is-paused", state === "paused");
  panel.classList.toggle("is-complete", state === "complete");
  refreshTerminalControls();
}

function playTerminalPanel(panel) {
  if (!terminalShowcase || terminalMotionQuery.matches) return;
  panel.classList.remove("is-running", "is-paused", "is-complete");
  panel.dataset.playbackState = "running";
  const body = panel.querySelector("[data-terminal-body]");
  if (body) body.scrollTop = 0;
  void panel.offsetWidth;
  panel.classList.add("is-running");
  refreshTerminalControls();
}

function selectTerminalPanel(key, shouldPlay = true) {
  terminalTabs.forEach((tab) => {
    const selected = tab.dataset.terminalTab === key;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
  });
  terminalPanels.forEach((panel) => {
    const selected = panel.dataset.terminalPanel === key;
    panel.hidden = !selected;
    if (selected && shouldPlay) playTerminalPanel(panel);
  });
}

if (terminalShowcase && terminalTabs.length && terminalPanels.length) {
  terminalTabs.forEach((tab, index) => {
    tab.tabIndex = tab.getAttribute("aria-selected") === "true" ? 0 : -1;
    tab.addEventListener("click", () => selectTerminalPanel(tab.dataset.terminalTab));
    tab.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      const offset = event.key === "ArrowRight" ? 1 : -1;
      const nextTab = terminalTabs[(index + offset + terminalTabs.length) % terminalTabs.length];
      selectTerminalPanel(nextTab.dataset.terminalTab);
      nextTab.focus();
    });
  });

  terminalPanels.forEach((panel) => {
    panel.dataset.playbackState = "running";
    panel.querySelector("[data-terminal-control]")?.addEventListener("click", () => {
      const state = panel.dataset.playbackState;
      if (state === "complete") {
        playTerminalPanel(panel);
        return;
      }
      setTerminalPlaybackState(panel, state === "paused" ? "running" : "paused");
    });
    panel.querySelector("[data-terminal-last]")?.addEventListener("animationend", (event) => {
      if (event.animationName === "terminal-line-in") setTerminalPlaybackState(panel, "complete");
    });
  });

  if (terminalMotionQuery.matches) {
    terminalPanels.forEach((panel) => setTerminalPlaybackState(panel, "complete"));
  } else {
    terminalShowcase.classList.add("terminal-showcase-enhanced");
    if ("IntersectionObserver" in window) {
      const terminalObserver = new IntersectionObserver((entries, observer) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        const panel = activeTerminalPanel();
        if (panel) playTerminalPanel(panel);
        observer.disconnect();
      }, { threshold: 0.28 });
      terminalObserver.observe(terminalShowcase);
    } else {
      const panel = activeTerminalPanel();
      if (panel) playTerminalPanel(panel);
    }
  }
  refreshTerminalControls();
}

const evidenceDialog = document.querySelector("[data-evidence-dialog]");
const evidenceViewport = document.querySelector("[data-evidence-viewport]");
const evidenceImage = document.querySelector("[data-evidence-image]");
const evidenceZoomOutput = document.querySelector("[data-evidence-zoom]");
const evidenceDialogTitle = document.querySelector("[data-evidence-dialog-title]");
const evidenceOriginal = document.querySelector("[data-evidence-original]");
let evidenceZoom = 100;
let evidenceBaseWidth = 0;
let evidenceBaseHeight = 0;
let dragStart = null;

function renderEvidenceZoom(nextZoom, preserveCenter = true) {
  if (!(evidenceViewport instanceof HTMLElement) || !(evidenceImage instanceof HTMLImageElement)) return;
  const next = Math.min(200, Math.max(50, nextZoom));
  const oldScrollWidth = Math.max(evidenceViewport.scrollWidth, 1);
  const oldScrollHeight = Math.max(evidenceViewport.scrollHeight, 1);
  const centerX = (evidenceViewport.scrollLeft + evidenceViewport.clientWidth / 2) / oldScrollWidth;
  const centerY = (evidenceViewport.scrollTop + evidenceViewport.clientHeight / 2) / oldScrollHeight;
  evidenceZoom = next;
  evidenceImage.style.width = `${evidenceBaseWidth * (next / 100)}px`;
  evidenceImage.style.height = `${evidenceBaseHeight * (next / 100)}px`;
  if (evidenceZoomOutput) evidenceZoomOutput.textContent = `${next}%`;
  window.requestAnimationFrame(() => {
    if (preserveCenter) {
      evidenceViewport.scrollLeft = centerX * evidenceViewport.scrollWidth - evidenceViewport.clientWidth / 2;
      evidenceViewport.scrollTop = centerY * evidenceViewport.scrollHeight - evidenceViewport.clientHeight / 2;
    } else {
      evidenceViewport.scrollTo({ left: 0, top: 0 });
    }
  });
}

function fitEvidenceImage() {
  if (!(evidenceViewport instanceof HTMLElement) || !(evidenceImage instanceof HTMLImageElement) || !evidenceImage.naturalWidth) return;
  const availableWidth = Math.max(240, evidenceViewport.clientWidth - 48);
  const availableHeight = Math.max(180, evidenceViewport.clientHeight - 48);
  const scale = Math.min(availableWidth / evidenceImage.naturalWidth, availableHeight / evidenceImage.naturalHeight, 1);
  evidenceBaseWidth = Math.round(evidenceImage.naturalWidth * scale);
  evidenceBaseHeight = Math.round(evidenceImage.naturalHeight * scale);
  renderEvidenceZoom(100, false);
}

document.querySelectorAll("[data-evidence-open]").forEach((trigger) => {
  trigger.addEventListener("click", () => {
    if (!(evidenceDialog instanceof HTMLDialogElement) || !(evidenceImage instanceof HTMLImageElement)) return;
    const src = trigger.dataset.evidenceSrc ?? "";
    const titleKey = trigger.dataset.evidenceTitleKey ?? "";
    const englishTitle = trigger.dataset.evidenceTitle ?? "Evidence trajectory";
    const translatedTitle = document.body.dataset.language === "zh" ? (zh[titleKey] ?? englishTitle) : englishTitle;
    evidenceImage.src = src;
    evidenceImage.alt = translatedTitle;
    if (evidenceDialogTitle) evidenceDialogTitle.textContent = translatedTitle;
    if (evidenceOriginal instanceof HTMLAnchorElement) evidenceOriginal.href = src;
    evidenceDialog.showModal();
    document.body.classList.add("dialog-open");
    if (evidenceImage.complete) window.requestAnimationFrame(fitEvidenceImage);
  });
});

if (evidenceImage instanceof HTMLImageElement) {
  evidenceImage.addEventListener("load", fitEvidenceImage);
}

if (evidenceDialog instanceof HTMLDialogElement) {
  evidenceDialog.addEventListener("click", (event) => {
    if (event.target === evidenceDialog) evidenceDialog.close();
  });
  evidenceDialog.addEventListener("close", () => {
    document.body.classList.remove("dialog-open");
    evidenceZoom = 100;
    dragStart = null;
  });
  evidenceDialog.querySelectorAll("[data-evidence-action]").forEach((control) => {
    control.addEventListener("click", () => {
      const action = control.dataset.evidenceAction;
      if (action === "zoom-out") renderEvidenceZoom(evidenceZoom - 25);
      if (action === "zoom-in") renderEvidenceZoom(evidenceZoom + 25);
      if (action === "reset") fitEvidenceImage();
      if (action === "close") evidenceDialog.close();
    });
  });
}

if (evidenceViewport instanceof HTMLElement) {
  evidenceViewport.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    dragStart = {
      x: event.clientX,
      y: event.clientY,
      left: evidenceViewport.scrollLeft,
      top: evidenceViewport.scrollTop,
    };
    evidenceViewport.classList.add("is-dragging");
    evidenceViewport.setPointerCapture(event.pointerId);
  });
  evidenceViewport.addEventListener("pointermove", (event) => {
    if (!dragStart) return;
    evidenceViewport.scrollLeft = dragStart.left - (event.clientX - dragStart.x);
    evidenceViewport.scrollTop = dragStart.top - (event.clientY - dragStart.y);
  });
  const endDrag = (event) => {
    dragStart = null;
    evidenceViewport.classList.remove("is-dragging");
    if (evidenceViewport.hasPointerCapture(event.pointerId)) evidenceViewport.releasePointerCapture(event.pointerId);
  };
  evidenceViewport.addEventListener("pointerup", endDrag);
  evidenceViewport.addEventListener("pointercancel", endDrag);
}

window.addEventListener("resize", () => {
  if (evidenceDialog instanceof HTMLDialogElement && evidenceDialog.open) fitEvidenceImage();
});

const revealTargets = document.querySelectorAll(".reveal");
if ("IntersectionObserver" in window && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      }
    }
  }, { rootMargin: "0px 0px -12%", threshold: 0.08 });
  revealTargets.forEach((target) => observer.observe(target));
} else {
  revealTargets.forEach((target) => target.classList.add("is-visible"));
}
