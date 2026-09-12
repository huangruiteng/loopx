/** Canonical projection-delivery state returned by Todo mutations. */
export type TodoProjectionDelivery = "pending" | "not_required";

/** Keep mutation results consistent and make the no-op meaning explicit. */
export function projectionDelivery(changed: boolean): TodoProjectionDelivery {
  return changed ? "pending" : "not_required";
}
