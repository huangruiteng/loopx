# Agent collaboration boundary

Any registered Agent can be a requester, worker or coordinator for a particular
exchange. These are relationships between requests, not privileged Agent types
or fixed hierarchy levels. A coordinator may request several peers; a receiver
may create another request using its received request as parent. Each conclusion
returns to its immediate requester. Only the original Chat request uses the
manager's conversation return adapter.

| Responsibility | Existing owner | This delivery |
| --- | --- | --- |
| Create/onboard an identity | `agent_onboarding.py`, `agent_registry.py`, registration CLI | Reuse registration; a request never creates an Agent |
| Connect a runtime and admit execution | Existing executor/binding, Turn and Goal/Todo/lease owners | Host explicitly binds Goal/Agent/workspace; requests do not launch workers or grant execution |
| Discover collaborators | `control_plane/agents/directory.py`, `agent-directory` | Existing same-Goal directory remains the discovery contract; registration is not presence |
| Validate semantic requests | `semantic_request.ts` | One typed validator for manager and peer callers |
| Retain requests, decisions and results | `inbox.py`, `peers.py` | Immutable identity, parent lineage, artifact versions, explicit result consumption |
| Sandboxed Agent access | `loopx/collaboration_mcp.py` | Same tools and identity binding at every coordination level |
| Owner conversation and external audience | `capabilities/manager_context` | Intent extraction, ingress grants, Chat/Lark routing and display; no peer scheduling |

The existing `manager-context` capability lifecycle, `manager-inbox` CLI and
`.local/manager-context` record address are retained for compatibility. They do
not make the manager an execution authority. Old Python entrypoints re-export
the moved shared functions for current callers. New peer/MCP callers import this
neutral boundary directly. No parallel task database, manager-only Agent factory,
new capability registration or speculative workflow engine is introduced.

Parent lineage retains root semantic context without recursively copying the
entire ancestor transcript. Immediate request ids keep each return unambiguous;
brief authors must preserve decision-relevant intermediate constraints. A parent
reference proves which request was received, not authority inheritance. Local
peer forwarding of external-audience parent requests is rejected.

`inbox.py` adapts the existing private file stores; typed request validation stays
in TypeScript. This does not promote a canonical shared-authority backend. General
request amendment/cancellation, cross-Goal/host delegation, dynamic Agent creation
and lifecycle supervision remain owned by their existing roadmap contracts.
The nested-coordinator regression and the [managed delivery demo](../../../examples/collaboration-delivery/README.md)
exercise this boundary without imposing a maximum tree depth or a manager hop.
