/** Complete advancement frontier identity and long-chain checkpoint policy.
 * Python supplies normalized legacy facts and the exact v0 serialization codec;
 * selection, completeness, hashing, thresholds and ACK authority live here.
 */
import { createHash } from "node:crypto";
import {inflateSync} from "node:zlib";
import type { JsonObject } from "../effect_program.ts";
import { requireJsonObject } from "../runtime_decode.ts";
import { EffectRuntimeRequestError } from "../effect_runtime_errors.ts";
import { parseTodoTimestampMicros } from "../runtime_timestamp.ts";
import { normalizeTodoAgent, stripPythonWhitespace } from "../coordination/todo_agents.ts";
import { AuthorityStoreProtocolError } from "../coordination/authority_store_codec.ts";

const REVISION = "todo_frontier_revision_v0";
const INDEX = "todo_frontier_revision_index_v0";
const TRIGGER = "long_todo_chain";
type Checkpoint = { complete: false } | {
  complete: true; frontier_revision: string; frontier_updated_at: string;
};
type Row = {
  id: string; claim: string | null; excluded: string[];
  updated: string; serialized: string; advancement: boolean;
};
type LongChainObservation = {
  trigger_count: number;
  count_kind: "selectable_advancement_todos" | "selectable_open_todos";
  selectable_open_count: number; selectable_advancement_count: number;
  current_agent_claimed_advancement_count: number; unclaimed_advancement_count: number;
  threshold: 15 | 20; agent_id: string | null;
  frontier_revision: string | null; frontier_revision_complete: boolean;
};
type AckDecision = {acknowledged: boolean; rearmed_after_obligation_id: string | null};
const object = (value: unknown): JsonObject =>
  value !== null && typeof value === "object" && !Array.isArray(value) ? value as JsonObject : {};
const text = (value: unknown): string => typeof value === "string" ? stripPythonWhitespace(value) : "";
function agentId(value: unknown): string | null {
  try { return normalizeTodoAgent(value, "agent_id"); }
  catch (error) {
    if (error instanceof AuthorityStoreProtocolError) return null;
    throw error;
  }
}
const strings = (value: unknown): string[] => Array.isArray(value)
  ? value.filter((item): item is string => typeof item === "string").map(item => item.trim()).filter(Boolean) : [];
const count = (value: unknown): number => {
  const number = Number(value ?? 0);
  return Number.isFinite(number) ? Math.max(0, Math.trunc(number)) : 0;
};

function decodeRows(value: unknown): Row[] | null {
  if (value == null) return null;
  if (!Array.isArray(value)) {
    const encoded = requireJsonObject(value, "frontier rows transport");
    if (encoded.encoding !== "deflate-base64-json-v0" || typeof encoded.data !== "string" ||
        encoded.data.length > 2 * 1024 * 1024 || !/^[A-Za-z0-9+/]+={0,2}$/.test(encoded.data)) {
      throw new EffectRuntimeRequestError("invalid frontier rows transport");
    }
    try {
      value = JSON.parse(inflateSync(Buffer.from(encoded.data, "base64"), {
        maxOutputLength: 64 * 1024 * 1024,
      }).toString("utf8"));
    } catch {
      throw new EffectRuntimeRequestError("frontier rows must be valid compressed JSON within 64 MiB");
    }
  }
  if (!Array.isArray(value)) throw new EffectRuntimeRequestError("frontier source must be an array");
  return value.map(raw => {
    const row = requireJsonObject(raw, "frontier row");
    if (typeof row.serialized !== "string" || typeof row.advancement !== "boolean") {
      throw new EffectRuntimeRequestError("frontier row codec facts are missing");
    }
    return {id: text(row.id), claim: text(row.claim) || null,
      excluded: strings(row.excluded), updated: text(row.updated),
      serialized: row.serialized, advancement: row.advancement};
  });
}

function checkpoint(rows: Row[] | null, agent: string | null, unclaimedOnly = false): Checkpoint {
  if (rows === null) return {complete: false};
  const selected = rows.filter(row => row.advancement &&
    (!unclaimedOnly || row.claim === null) &&
    (!agent || ((row.claim === null || row.claim === agent) && !row.excluded.includes(agent))));
  if (selected.length === 0) return {complete: false};
  const ids = new Set<string>();
  let latest: bigint | null = null;
  let updated = "";
  for (const row of selected) {
    const instant = parseTodoTimestampMicros(row.updated);
    if (!row.id || ids.has(row.id) || instant === null) return {complete: false};
    ids.add(row.id);
    if (latest === null || instant > latest) { latest = instant; updated = row.updated; }
  }
  selected.sort((a, b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
  const digest = createHash("sha256").update(`[${selected.map(row => row.serialized).join(",")}]`).digest("hex");
  return {complete: true, frontier_revision: `${REVISION}:${digest.slice(0, 24)}`,
    frontier_updated_at: updated};
}

function readIndex(value: unknown, agent: string | null): Checkpoint | null {
  if (value === null || value === undefined || typeof value !== "object" || Array.isArray(value)) return null;
  const index = object(value);
  if (index.schema_version !== INDEX) return {complete: false};
  let raw = index.all;
  if (agent) {
    if (!Array.isArray(index.by_agent)) return {complete: false};
    const matches = index.by_agent.filter(row => agentId(object(row).agent_id) === agent);
    if (matches.length > 1) return {complete: false};
    raw = matches[0] ?? index.unclaimed;
  }
  const entry = object(raw);
  const revision = text(entry.frontier_revision), updated = text(entry.frontier_updated_at);
  if (entry.complete !== true || !revision || parseTodoTimestampMicros(updated) === null) return {complete: false};
  return {complete: true, frontier_revision: revision, frontier_updated_at: updated};
}

export function projectAdvancementFrontier(value: unknown): JsonObject {
  const request = requireJsonObject(value, "frontier revision request");
  if (request.schema_version !== "todo_frontier_revision_request_v0") throw new EffectRuntimeRequestError("frontier revision schema mismatch");
  const agent = agentId(request.agent_id);
  if (request.operation === "read") return {checkpoint: readIndex(request.index, agent)};
  const rows = decodeRows(request.rows);
  if (request.operation === "select") return {checkpoint: checkpoint(rows, agent)};
  if (request.operation !== "index") throw new EffectRuntimeRequestError("unsupported frontier revision operation");
  // An excluded agent can have no claimed rows. It still needs its own lane;
  // falling back to the global unclaimed checkpoint would include excluded work.
  const agents = [...new Set((rows ?? []).filter(row => row.advancement)
    .flatMap(row => [...(row.claim ? [row.claim] : []), ...row.excluded]))].sort();
  return {index: {schema_version: INDEX, all: checkpoint(rows, null),
    unclaimed: checkpoint(rows, null, true),
    by_agent: agents.map(agent_id => ({agent_id, ...checkpoint(rows, agent_id)}))}};
}

function classifyAck(observation: LongChainObservation, value: unknown): AckDecision {
  const ack = object(value), delta = object(ack.semantic_delta);
  const id = text(delta.obligation_id);
  const rejected = {acknowledged: false, rearmed_after_obligation_id: null};
  if (ack.recorded !== true || delta.accepted !== true ||
      !strings(delta.trigger_kinds).includes(TRIGGER) || !/^replan-[a-f0-9]{16}$/.test(id) ||
      observation.frontier_revision_complete !== true || !text(observation.frontier_revision)) return rejected;
  const matches = Array.isArray(delta.trigger_checkpoints) && delta.trigger_checkpoints.some(raw => {
    const row = object(raw);
    return text(row.kind) === TRIGGER && text(row.frontier_revision) === observation.frontier_revision;
  });
  return {acknowledged: matches, rearmed_after_obligation_id: matches ? null : id};
}

export function evaluateLongTodoChain(value: unknown): JsonObject {
  const request = requireJsonObject(value, "long chain request");
  if (request.schema_version !== "long_todo_chain_request_v0") throw new EffectRuntimeRequestError("long chain schema mismatch");
  if (request.operation !== "observe") throw new EffectRuntimeRequestError("unsupported long chain operation");
  const summary = object(request.summary), frontier = object(request.frontier_counts);
  const current = count(frontier.current_agent_claimed_advancement_count);
  const unclaimed = count(frontier.unclaimed_advancement_count);
  const advancement = current + unclaimed;
  const open = Math.max(advancement, request.summary == null ? count(object(request.agent_counts).open) :
    count(summary.current_agent_claimed_open_count) + count(summary.unclaimed_open_count));
  const threshold = advancement >= 15 ? 15 : open >= 20 && advancement > 0 ? 20 : null;
  if (threshold === null) return {observation: null, decision: null};
  const agent = agentId(request.agent_id);
  const revision = readIndex(summary.advancement_frontier_revision_index, agent)
    ?? checkpoint(decodeRows(request.rows), agent);
  const observation: LongChainObservation = {trigger_count: threshold === 15 ? advancement : open,
    count_kind: threshold === 15 ? "selectable_advancement_todos" : "selectable_open_todos",
    selectable_open_count: open, selectable_advancement_count: advancement,
    current_agent_claimed_advancement_count: current, unclaimed_advancement_count: unclaimed,
    threshold, agent_id: agent, frontier_revision: revision.complete ? revision.frontier_revision : null,
    frontier_revision_complete: revision.complete};
  return {observation, decision: classifyAck(observation, request.ack)};
}
