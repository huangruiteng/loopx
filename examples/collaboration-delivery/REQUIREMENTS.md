# Allocation planner

Implement `python solver.py inputs/scenario.json outputs/plan.json` using exact
integer arithmetic. Maximize total value under individual demand, shared group
stock, region capacity and total integer-cent budget. Among optimal solutions,
choose the lexicographically smallest allocation vector in sorted order-id order.
Output `allocation` (id → integer), `total_value` and `total_cost`.

Every declared group retains `reserve_per_group` units: its allocation limit is
`max(0, stock - reserve_per_group)`. Total East allocation must be at least
`minimum_east`. A zero-demand order receives zero even if its value is high.
`reserve_per_group` and `minimum_east` are optional and default to zero when omitted.
All other required input fields must be present. Reject malformed or infeasible inputs with nonzero exit and no success plan.
Booleans, fractional numbers, negative quantities, duplicate ids and missing
stock/region declarations are malformed. All quantities/costs/values are
nonnegative integers; use no floating-point optimization.

The owner rejected proportional rounding: it can violate coupled constraints
or miss the optimum. Do not place orders or use external services. Independent
review must open actual artifacts, derive expectations and run the solver;
model/builder claims alone do not establish correctness.
