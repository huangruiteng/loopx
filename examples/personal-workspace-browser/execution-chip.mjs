import { resolve } from "node:path";

import { outputDir } from "./fixture.mjs";
import { openWorkspacePage } from "./scenario-context.mjs";

// The shipped steward binding: the channel selected the interactive CLI endpoint,
// which is billed to an individual CLI login, and kept the vendor model default.
const shippedBinding = {
  schema_version: "manager_channel_binding_v0",
  executor_endpoint: "codex",
  executor_endpoint_source: "product_default",
  executor_kind: "individual",
  model: "gpt-6-astra",
  model_source: "vendor_default",
  credential_env_var: "",
  operator_credential_configured: true,
  available: null,
  unavailable_reason: null,
};

// The operator explicitly pointed the channel at the managed host, which has no
// interactive Chat transport yet, so the binding resolves but reports it.
const managedHostBinding = {
  ...shippedBinding,
  executor_endpoint: "dsh",
  executor_endpoint_source: "explicit_config",
  executor_kind: "managed",
  credential_env_var: "DEEPSEEK_API_KEY",
  available: false,
  unavailable_reason: "managed_host_chat_transport_unsupported",
};

// An endpoint the control plane reports no kind for must not be labelled as a
// kind the operator can act on, and an unrecognized model source must not be
// reported as the vendor default.
const unknownKindBinding = {
  ...shippedBinding,
  executor_endpoint: "pi",
  executor_endpoint_source: "explicit_config",
  executor_kind: "",
  model_source: "unrecognized_source",
};

async function openChip(browser, url, binding, collectCoverage) {
  const context = await openWorkspacePage(browser, url, {
    apiOptions: { managerChannelBinding: binding },
    collectCoverage,
  });
  try {
    await context.page.locator(".personal-execution-chip").waitFor({ state: "visible" });
    return context;
  } catch (error) {
    await context.page.screenshot({
      animations: "disabled",
      fullPage: false,
      path: resolve(outputDir, "execution-chip-failed.png"),
    });
    await context.close();
    throw error;
  }
}

async function chipText(page) {
  return (await page.locator(".personal-execution-chip").innerText()).replace(/\s+/g, " ").trim();
}

async function assertHairlineRow(page) {
  const headerBox = await page.locator(".personal-channel-header").boundingBox();
  const chipBox = await page.locator(".personal-execution-chip").boundingBox();
  if (!headerBox || !chipBox) throw new Error("Execution chip has no layout box");
  if (chipBox.y < headerBox.y || chipBox.y + chipBox.height > headerBox.y + headerBox.height) {
    throw new Error("Execution chip escaped the channel header row");
  }
  if (chipBox.height > 26) {
    throw new Error(`Execution chip is not a compact hairline row: ${chipBox.height}px tall`);
  }
}

export const executionChipScenario = {
  id: "execution-chip",
  async run({ browser, collectCoverage, url }) {
    const shipped = await openChip(browser, url, shippedBinding, collectCoverage);
    const { close, coverageEntries, page } = shipped;
    try {
      const text = await chipText(page);
      for (const fragment of ["codex", "gpt-6-astra", "个人 CLI 登录"]) {
        if (!text.includes(fragment)) {
          throw new Error(`Execution chip omitted ${fragment}: ${text}`);
        }
      }
      if (text.includes("deepseek")) {
        throw new Error(`Selecting the CLI endpoint must not move the model: ${text}`);
      }
      if (await page.locator(".personal-execution-note").count() !== 0) {
        throw new Error("A usable steward channel must not render an unavailability note");
      }
      await assertHairlineRow(page);
      await page.screenshot({
        animations: "disabled",
        fullPage: false,
        path: resolve(outputDir, "execution-chip-manager-header.png"),
      });
    } finally {
      await close();
    }

    // A destination with no Chat transport resolves, reports, and says so.
    const managed = await openChip(browser, url, managedHostBinding, collectCoverage);
    try {
      const text = await chipText(managed.page);
      if (!text.includes("dsh") || !text.includes("operator 凭据")) {
        throw new Error(`Managed host chip did not report its credential bound: ${text}`);
      }
      const note = managed.page.locator(".personal-execution-note");
      await note.waitFor({ state: "visible" });
      const noteText = (await note.innerText()).replace(/\s+/g, " ").trim();
      if (!noteText.includes("尚无 Chat 通道") || !noteText.includes("dsh")) {
        throw new Error(`Transport note did not name the pending managed host: ${noteText}`);
      }
      if (await managed.page.locator(".personal-execution-chip.is-unavailable").count() !== 1) {
        throw new Error("An unavailable steward executor did not mark its chip as unavailable");
      }
      await assertHairlineRow(managed.page);
    } finally {
      coverageEntries.push(...await managed.close());
    }

    // An endpoint with no reported kind, and a model source this build does not
    // recognize, must both stay visibly unclaimed rather than invent a fact.
    const unknown = await openChip(browser, url, unknownKindBinding, collectCoverage);
    try {
      const text = await chipText(unknown.page);
      if (!text.includes("pi") || !text.includes("注册端点")) {
        throw new Error(`Execution chip omitted the selected endpoint: ${text}`);
      }
      for (const invented of ["个人 CLI 登录", "operator 凭据"]) {
        if (text.includes(invented)) {
          throw new Error(`Unknown executor kind was reported as ${invented}: ${text}`);
        }
      }
      await assertHairlineRow(unknown.page);
    } finally {
      coverageEntries.push(...await unknown.close());
    }

    // A control plane that projects no binding keeps the previous header.
    const withoutBinding = await openWorkspacePage(browser, url, { collectCoverage });
    try {
      if (await withoutBinding.page.locator(".personal-execution-chip").count() !== 0) {
        throw new Error("Execution chip rendered without a projected channel binding");
      }
    } finally {
      coverageEntries.push(...await withoutBinding.close());
    }

    // The narrow header hides its subtitle row, so the chip may be out of view
    // there; if it is shown it must still fit inside the viewport, and an
    // unavailable executor must keep its reason readable instead of collapsing.
    const mobile = await openWorkspacePage(browser, url, {
      apiOptions: { managerChannelBinding: shippedBinding },
      collectCoverage,
      isMobile: true,
      viewport: { width: 390, height: 844 },
    });
    try {
      const mobileChip = mobile.page.locator(".personal-execution-chip");
      if (await mobileChip.isVisible()) {
        const chipBox = await mobileChip.boundingBox();
        const viewport = mobile.page.viewportSize();
        if (!chipBox || !viewport || chipBox.x + chipBox.width > viewport.width) {
          throw new Error("Execution chip overflows the mobile viewport");
        }
      }
    } finally {
      coverageEntries.push(...await mobile.close());
    }

    const mobileUnavailable = await openWorkspacePage(browser, url, {
      apiOptions: { managerChannelBinding: managedHostBinding },
      collectCoverage,
      isMobile: true,
      viewport: { width: 390, height: 844 },
    });
    try {
      const note = mobileUnavailable.page.locator(".personal-execution-note");
      await note.waitFor({ state: "visible" });
      const noteBox = await note.boundingBox();
      if (!noteBox || noteBox.width < 40) {
        throw new Error(`Unavailable transport reason collapsed in the narrow header: ${JSON.stringify(noteBox)}`);
      }
    } finally {
      coverageEntries.push(...await mobileUnavailable.close());
    }
    return {
      coverageEntries,
      note: "execution chip reports the selected executor, the credential it is billed to and the resolved model, names a missing Chat transport, and stays absent without a binding",
    };
  },
};
