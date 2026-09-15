/**
 * One owner for the goal rollout-event log location and its receipt reads.
 *
 * The log is a goal-level runtime artifact that more than one transaction
 * reads: the settlement readback, the receipt-bound scheduler follow-up, and
 * prior-host-Turn closeout resolution.  Resolving the path and reading its
 * receipts lives here so a reader cannot invent a second path rule or a
 * different tolerance for malformed lines.
 */
import { readFile } from "node:fs/promises";
import { relative, resolve, sep } from "node:path";

import type { JsonObject } from "./effect_program.ts";
import { EffectRuntimeRequestError } from "./effect_runtime_errors.ts";
import { jsonObject, requireNonEmptyString } from "./runtime_decode.ts";

export const ROLLOUT_EVENT_SCHEMA_VERSION = "loopx_rollout_event_v0";
export const HEARTBEAT_RECEIPT_EVENT_KIND = "quota_should_run";

/** Reject a goal id that is not one path segment, before any log read. */
export function goalPathSegment(value: unknown): string {
  const label = "goal_id";
  const result = requireNonEmptyString(value, label).trim();
  if (
    result === "." ||
    result === ".." ||
    result.includes("/") ||
    result.includes("\\")
  ) {
    throw new EffectRuntimeRequestError(
      `${label} must be a single path segment`,
      "invalid_goal_id",
    );
  }
  return result;
}

/** Resolve one goal's rollout-event log inside `runtime_root`. */
export function goalRolloutEventLogPath(
  runtimeRoot: string,
  goalId: string,
): string {
  const root = resolve(runtimeRoot);
  const path = resolve(
    root,
    "goals",
    goalPathSegment(goalId),
    "rollout-event-log.jsonl",
  );
  const child = relative(root, path);
  if (child === "" || child === ".." || child.startsWith(`..${sep}`)) {
    throw new EffectRuntimeRequestError(
      "rollout event log path escapes runtime_root",
      "invalid_rollout_event_log_path",
    );
  }
  return path;
}

/**
 * Read the heartbeat receipts this goal persisted for one Agent.
 *
 * The read mirrors the established non-strict reader: a malformed or
 * differently versioned line is skipped rather than allowed to erase or
 * manufacture a receipt, and an absent log is `null` because "no receipts yet"
 * and "no log yet" are different facts for a caller that must report state.
 */
export async function readGoalHeartbeatReceipts(
  runtimeRoot: string,
  goalId: string,
  agentId?: string | null,
): Promise<JsonObject[] | null> {
  let text: string;
  try {
    text = await readFile(goalRolloutEventLogPath(runtimeRoot, goalId), "utf8");
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw error;
  }
  const receipts: JsonObject[] = [];
  for (const line of text.split(/\r?\n/)) {
    if (!line.trim()) continue;
    try {
      const event = jsonObject(JSON.parse(line));
      if (
        event?.schema_version === ROLLOUT_EVENT_SCHEMA_VERSION &&
        event.event_kind === HEARTBEAT_RECEIPT_EVENT_KIND &&
        event.goal_id === goalId &&
        (agentId === undefined || event.agent_id === agentId)
      ) {
        receipts.push(event);
      }
    } catch {
      // Match the established non-strict rollout-event reader: unrelated
      // malformed lines do not manufacture or erase a valid receipt.
    }
  }
  return receipts;
}
