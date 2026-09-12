export const DEFAULT_EFFECT_RUNTIME_IDLE_MS = 5 * 60 * 1_000;
export const MAX_EFFECT_RUNTIME_IDLE_MS = 2_147_483_647;

export function effectRuntimeIdleMs(value: string | undefined): number {
  if (value === undefined) return DEFAULT_EFFECT_RUNTIME_IDLE_MS;
  const normalized = value.trim();
  if (!/^\d+$/u.test(normalized)) {
    throw new Error(
      "LOOPX_EFFECT_RUNTIME_IDLE_MS must be a positive base-10 integer",
    );
  }
  const parsed = Number(normalized);
  if (
    !Number.isSafeInteger(parsed) || parsed < 1 ||
    parsed > MAX_EFFECT_RUNTIME_IDLE_MS
  ) {
    throw new Error(
      `LOOPX_EFFECT_RUNTIME_IDLE_MS must be between 1 and ${MAX_EFFECT_RUNTIME_IDLE_MS}`,
    );
  }
  return parsed;
}
