import assert from "node:assert/strict";
import {
  agentFamily,
  presentedAgentFamily,
} from "../../../node_modules/.cache/loopx-agent-family/agent-family.js";

// Positive: every documented shape still resolves to its host family, so a
// built-in Endpoint keeps its label.
assert.equal(agentFamily("kiro"), "kiro");
assert.equal(agentFamily("kiro-cli"), "kiro");
assert.equal(agentFamily("kiro_cli"), "kiro");
assert.equal(agentFamily("Kiro-Worker-1"), "kiro");
assert.equal(agentFamily("codex"), "codex");
assert.equal(agentFamily("codex-main-control"), "codex");
assert.equal(agentFamily("claude-code"), "claude");

// Negative: an unrelated operator id that merely begins with a family root
// keeps its own identity, matching the backend. Displaying it as the host would
// attribute another agent's work to Kiro/Codex/Claude.
assert.equal(agentFamily("kiroscope-worker"), "kiroscope-worker");
assert.equal(agentFamily("kirograph"), "kirograph");
assert.equal(agentFamily("codexplorer"), "codexplorer");
assert.equal(agentFamily("claudeflow"), "claudeflow");

// The typed adapter kind wins over the operator-chosen id when present, and the
// generic transport/projection placeholders are not treated as family signals.
assert.equal(presentedAgentFamily("kiroscope-worker", "kiro-cli"), "kiro");
assert.equal(presentedAgentFamily("kiroscope-worker", null), "kiroscope-worker");
assert.equal(presentedAgentFamily("kiroscope-worker", ""), "kiroscope-worker");
assert.equal(
  presentedAgentFamily("kiroscope-worker", "status_projection"),
  "kiroscope-worker",
);
assert.equal(presentedAgentFamily("kiro-cli", "acp"), "kiro");
assert.equal(presentedAgentFamily("custom-worker", "acp"), "custom-worker");

console.log("Agent family presentation invariants passed");
