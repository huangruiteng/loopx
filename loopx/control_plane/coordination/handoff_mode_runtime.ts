/** Local transport binds the existing provider and writer fence to the mode transaction. */
import type {JsonObject} from "../effect_program.ts";
import {requireJsonObject} from "../runtime_decode.ts";
import {requireAuthorityStoreId} from "./authority_store_codec.ts";
import {openLocalAuthorityStore, localAuthorityOpenFailure} from "./local_authority_provider.ts";
import {runtimeRoot, sourceAuthorityFor, withCanonicalWriter} from "./local_authority_runtime.ts";
import {ShadowManagementError} from "./shadow_management.ts";
import {executeHandoffModeSet, HANDOFF_MODE_SET_SCHEMA} from "./handoff_mode_transaction.ts";

export async function setLocalHandoffMode(value: unknown): Promise<JsonObject> {
  const evidence = {source_authority: "file_v0", decision_read_from_provider: true, legacy_fallback_used: false};
  try {
    const input = requireJsonObject(value, "handoff mode set request");
    if (input.schema_version !== HANDOFF_MODE_SET_SCHEMA) throw new Error("handoff mode request schema mismatch");
    const root = runtimeRoot(input.runtime_root);
    const goalId = requireAuthorityStoreId(input.goal_id, "goal id");
    return await withCanonicalWriter(root, goalId, input.dry_run === true, async () => {
      const store = await openLocalAuthorityStore(root, goalId);
      evidence.source_authority = sourceAuthorityFor(store);
      return {...await executeHandoffModeSet(store, {goal_id: goalId,
        operation_id: input.operation_id as string, requested_mode: input.requested_mode as string,
        observed_at: input.observed_at as string, dry_run: input.dry_run as boolean}), ...evidence};
    });
  } catch (error) {
    return {schema_version: "loopx_coordination_handoff_mode_set_result_v0", status: "failed", changed: false,
      reason_code: error instanceof ShadowManagementError ? error.reason_code : "handoff_mode_unavailable",
      reason: error instanceof Error ? error.message : String(error), ...evidence, ...localAuthorityOpenFailure(error)};
  }
}
