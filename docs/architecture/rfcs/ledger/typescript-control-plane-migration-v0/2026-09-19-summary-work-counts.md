# Summary work-count consumer closure (2026-09-19)

| Boundary | Delivered evidence |
| --- | --- |
| Goal/source | Overall roadmap R5/S2, TS T3 and shared-authority L5; baseline `96d98f3d4`. |
| Observable gap | A complete source with 21 actionable advancement Todos becomes 8 when a consumer counts the bounded backlog; quota payload compaction reduces the apparent count further. A different legacy fallback classifies unseen rows as advancement. |
| Owning change | `todos/summary_lanes.ts` selects lanes in one typed batch and supplies pre-limit work counts. Existing quota selection reuses the count owner after Agent filtering. Python retains normalization, timestamp/presentation adaptation and ordinal readback; its lane-selection and hidden-work inference loops are removed. |
| Semantics | Complete counts survive list/status/quota compaction. Incomplete scope knowledge survives repeated projection; contradictory legacy fragments cannot prove completeness. Unknown tasks are not inferred as executable. Canonical `todo list` carries the read revision's acceptance guard, matching status without hiding held records. |
| Compatibility | Full baseline/candidate role and scoped summaries agree apart from the disclosed additive counts; completed/deferred conventions, ordering, Monitor timing and successor/closure policies remain. Empty canonical sources stay authoritative and unavailable providers cannot fall back to Markdown. |
| Real paths | File/SQLite CLI and installed-wheel CLI/Chat HTTP readback; isolated real PostgreSQL authority/service reads; both complete synthetic record schemas and an authorized frozen full-graph snapshot. Existing heads/Todos/leases and independent display bytes remain unchanged. |
| Cost | Two compact ordinal-planning requests per two-role summary; no per-Todo RPC and no new persisted queue or provider state. The whole Python summary adapter still has other rule/effect callers. |
| Remaining boundary | This closes the count consumer within L5, not permanent projection freshness, all T3 sources, event callers, executor-held effect fences, D2 capacity/elapsed soak or D3 integrated promotion. No default change or old-writer retirement is claimed. |

See [the read contract](../../../../reference/todo-work-counts.md) for field
meaning, public read commands, incomplete-source behavior and rollback.
