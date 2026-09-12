/** Canonical projection-delivery state returned by Todo mutations. */
export type TodoProjectionDelivery = "pending" | "delivered" | "current" | "not_required";
const PROJECTION_DELIVERY_VALUES = new Set<TodoProjectionDelivery>([
  "pending", "delivered", "current", "not_required",
]);

/** Keep mutation results consistent and make the no-op meaning explicit. */
export function projectionDelivery(changed: boolean): TodoProjectionDelivery {
  return changed ? "pending" : "not_required";
}

/** Decode provider readback without letting ad-hoc strings cross the boundary. */
export function parseProjectionDelivery(value: unknown): TodoProjectionDelivery {
  if (typeof value === "string" && PROJECTION_DELIVERY_VALUES.has(value as TodoProjectionDelivery)) {
    return value;
  }
  throw new Error(`projection_delivery is unsupported: ${String(value)}`);
}

export function isProjectionDelivery(value: unknown): value is TodoProjectionDelivery {
  return typeof value === "string" && PROJECTION_DELIVERY_VALUES.has(value as TodoProjectionDelivery);
}
