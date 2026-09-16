// Browser acceptance for confirming a validated steward team plan.
//
// The unit smoke proves the transport accepts the kind and that the reducer
// renders the lanes. This scenario proves the click path an owner actually
// takes: a validated multi-lane preview becomes a card, the card shows every
// lane and its gap, and confirming it sends exactly one apply.

import { resolve } from "node:path";

import { outputDir } from "./fixture.mjs";
import { openWorkspacePage } from "./scenario-context.mjs";

const GOAL_ID = "product-release";
const PROPOSAL_ID = "proposal-team-plan-fixture";
const MANAGER_PROPOSAL_ID = "proposal-team-plan-manager-fixture";
// The manager-channel card is deliberately a different plan from the Goal-scoped
// one, so a row in the manager conversation cannot be the Goal's card leaking in.
const MANAGER_PROPOSAL_TITLE = "为 product-release 配出 3 条 lane 的团队";
const READY_TODO = "Implement the bounded intake";
const GAP_TODO = "Independently review the intake";

function teamPlanProposal() {
  return {
    schema_version: "loopx_chat_action_proposal_v1",
    proposal_id: PROPOSAL_ID,
    action_kind: "team.plan",
    summary: "为 product-release 配出 2 条 lane 的团队",
    normalized_parameters: {
      goal_id: GOAL_ID,
      plan: {
        schema_version: "steward_team_plan_preview_v0",
        kind: "steward_team_plan_preview",
        goal_id: GOAL_ID,
        objective: "Ship the bounded intake",
        lanes: [
          {
            lane_id: "lane_intake",
            agent_id: "agent-backend",
            acceptance: "the bounded Todo is created through the canonical owner",
            staffing: "ready",
            first_todo: {
              text: READY_TODO,
              priority: "P1",
              task_class: "advancement_task",
              action_kind: "implement",
            },
          },
          {
            lane_id: "lane_review",
            agent_id: "agent-reviewer",
            acceptance: "the review receipt is recorded",
            staffing: "gap",
            gap_reason_code: "agent_not_registered",
            declined_first_todo: {
              text: GAP_TODO,
              priority: "P1",
              task_class: "advancement_task",
              action_kind: "validate",
            },
          },
        ],
        gaps: [{ lane_id: "lane_review", reason_code: "agent_not_registered" }],
        quota_envelope: { slots: 4, window: "1d" },
        stop_condition: "every lane reports a typed outcome or a stated gap",
        applies: false,
      },
      requested_by: "owner",
    },
    context: { kind: "goal", goal_id: GOAL_ID },
    expected_state_fingerprint: "fixture-team-plan-r1",
    permission_classification: "durable_write",
    validation_evidence: ["every ready lane names an Agent this Goal registers"],
    available_transitions: ["apply", "cancel"],
    status: "preview_ready",
    receipt: null,
    stale: null,
    created_at: "2026-09-16T01:00:00Z",
    updated_at: "2026-09-16T01:00:01Z",
  };
}

/**
 * The same plan as the manager channel stored it.
 *
 * A plan the steward offers from the manager conversation is stored by that
 * channel, and its card has to be confirmable in the conversation that produced
 * it -- not only under the Goal whose workspace it is scoped to.
 */
function managerTeamPlanProposal() {
  const plan = teamPlanProposal();
  const parameters = plan.normalized_parameters;
  return {
    ...plan,
    proposal_id: MANAGER_PROPOSAL_ID,
    summary: MANAGER_PROPOSAL_TITLE,
    context: { kind: "manager", goal_id: GOAL_ID },
    normalized_parameters: {
      ...parameters,
      plan: {
        ...parameters.plan,
        objective: "Ship the manager-channel intake",
        lanes: [
          ...parameters.plan.lanes,
          {
            lane_id: "lane_manager",
            agent_id: "agent-manager",
            acceptance: "the manager lane reports its receipt",
            staffing: "ready",
            first_todo: {
              text: "Review the steward handoff",
              priority: "P2",
              task_class: "advancement_task",
              action_kind: "validate",
            },
          },
        ],
      },
    },
  };
}

export const teamPlanScenario = {
  id: "team-plan",
  async run({ browser, collectCoverage, url }) {
    const failures = [];
    const notes = [];
    const check = (condition, message) => {
      if (condition) notes.push(message);
      else failures.push(message);
    };
    const context = await openWorkspacePage(browser, url, {
      apiOptions: { initialActionProposals: [teamPlanProposal(), managerTeamPlanProposal()] },
      collectCoverage,
    });
    try {
      const { api, page } = context;
      // Only the product's own API calls are asserted here: the development
      // server may refuse to serve an asset it considers outside its root,
      // which is a harness path question rather than a client failure.
      const failedResponses = [];
      page.on("response", (response) => {
        if (response.status() >= 400 && response.url().includes("/api/")) {
          failedResponses.push(`${response.status()} ${response.url()}`);
        }
      });
      await page.locator(".personal-goal-link", { hasText: "Product Release" }).click();
      await page.locator(".personal-goal-tabs button", { hasText: "Chat" }).click();

      const row = page.locator(".personal-proposal-row", { hasText: "配出 2 条 lane" });
      try {
        await row.waitFor({ state: "visible", timeout: 15_000 });
      } catch (error) {
        throw new Error(
          `${error.message}; rows=${JSON.stringify(await page.locator(".personal-proposal-row").allInnerTexts())};`
          + ` body=${(await page.locator("body").innerText()).slice(0, 1500)}`,
        );
      }
      check((await row.innerText()).includes("team.plan"), "the proposal row names the team.plan action kind");

      await row.click();
      const drawer = page.locator('.personal-context-drawer[data-context-kind="proposal"]');
      await drawer.getByText("配额包络", { exact: true }).waitFor({ state: "visible", timeout: 15_000 });
      const previewText = await drawer.innerText();
      check(previewText.includes("agent-backend"), "a ready lane names the Agent that runs it");
      check(
        previewText.includes(`P1 · implement · ${READY_TODO}`),
        "a ready lane shows its first bounded Todo with its priority and action kind",
      );
      check(
        previewText.includes("验收: the bounded Todo is created through the canonical owner"),
        "a ready lane shows its acceptance signal",
      );
      check(
        previewText.includes("agent-reviewer")
        && previewText.includes("未配齐")
        && previewText.includes("agent_not_registered")
        && previewText.includes(GAP_TODO),
        "a gap lane says it is unstaffed, names the reason, and keeps the work it did not staff",
      );
      check(
        previewText.includes("配额包络") && previewText.includes("slots: 4") && previewText.includes("停止条件"),
        "the quota envelope and the stop condition render",
      );
      check(previewText.includes("确认后会通过既有 owner"), "the card states what confirming does");
      check(
        !/(已创建|已经创建|lanes created|已组建)/u.test(previewText),
        "the card never claims a lane already exists before confirmation",
      );
      await page.screenshot({
        path: resolve(outputDir, "team-plan-preview.png"),
        fullPage: false,
        animations: "disabled",
      });

      const confirm = drawer.getByRole("button", { name: "确认并组建各 lane", exact: true });
      check(await confirm.count() === 1, "exactly one confirmation control is offered");
      check(await confirm.isEnabled(), "the validated preview is confirmable");
      await confirm.click();

      for (let attempt = 0; attempt < 60 && api.actionApplies.length === 0; attempt += 1) {
        await page.waitForTimeout(50);
      }
      check(
        api.actionApplies.filter((proposalId) => proposalId === PROPOSAL_ID).length === 1,
        "confirming sends exactly one apply for the confirmed proposal",
      );
      check(api.durableWriteCount === 1, "the confirmed apply performed exactly one durable write");
      await drawer.getByText("已应用，LoopX 状态将刷新。", { exact: true })
        .waitFor({ state: "visible", timeout: 15_000 });
      await page.screenshot({
        path: resolve(outputDir, "team-plan-applied.png"),
        fullPage: false,
        animations: "disabled",
      });

      // The manager conversation offers the card its own channel produced, so a
      // plan asked for there is confirmable there instead of only under the Goal
      // it staffs. The Goal-scoped card stays in that Goal's workspace.
      await page.locator(".personal-manager-link").first().click();
      await page.locator(".personal-goal-tabs button", { hasText: "Chat" }).click();
      const managerCard = page.locator(".personal-proposal-row", { hasText: MANAGER_PROPOSAL_TITLE });
      try {
        await managerCard.waitFor({ state: "visible", timeout: 15_000 });
      } catch (error) {
        throw new Error(
          `${error.message}; manager rows=${JSON.stringify(await page.locator(".personal-proposal-row").allInnerTexts())};`
          + ` body=${(await page.locator("body").innerText()).slice(0, 1200)}`,
        );
      }
      check(
        (await managerCard.innerText()).includes("team.plan"),
        "the manager conversation offers the team plan card it produced",
      );
      await page.screenshot({
        path: resolve(outputDir, "team-plan-manager-conversation.png"),
        fullPage: false,
        animations: "disabled",
      });
      // The harness collects both uncaught page errors and console errors; a
      // dev-server resource status is not a client-side exception, so only the
      // former is a failure here.
      const scriptErrors = context.errors.filter((message) => !message.startsWith("Failed to load resource"));
      check(
        scriptErrors.length === 0,
        `no client-side exception was raised (${scriptErrors.join(" | ")})`,
      );
      check(
        failedResponses.length === 0,
        `no LoopX API call failed while confirming the plan (${failedResponses.join(" | ")})`,
      );
    } finally {
      await context.close();
    }
    if (failures.length) throw new Error(failures.join(" | "));
    return { coverageEntries: context.coverageEntries, note: notes.join(" ") };
  },
};
