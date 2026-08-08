# Finance Value Discovery

Status: co-located optional LoopX extension sample.

## Placement

- extension id: `loopx-finance-value-discovery`
- capability registration: none
- placement: `packages/loopx-finance-value-discovery/`

This optional workflow owns its command and packet contract. LoopX does not
need a provider-neutral finance capability, so installing the extension must
not add `finance-value-discovery` to the capability catalog. The package owns
its dependencies, installation, doctor, enablement, and upgrade lifecycle.

## Contract

The reducer accepts a frozen `finance_value_discovery_input_v0` object and
emits `finance_value_discovery_packet_v0`. It performs no network request. A
separate collector may prepare public evidence cards, but connector output is
input evidence, not accepted truth.

The additive [`finance_case_contract_v1`](CONTRACT.md) surface separates a
method's frozen contract from provider observations. Its deterministic gate
engine stops at the first failed, missing, or conflicting gate. The replay
harness binds the contract, input, and result with canonical SHA-256 receipts.
Passing every gate means only that a case is eligible for a bounded research
successor; it cannot promote a revision, advise, or trade.

Two P1 overlays reuse that contract without weakening it:

- `finance_beta_attribution_input_v1` decomposes a frozen total move into
  market, rate, sector, narrow-peer, cycle, event, and computed residual
  layers. If any explained component is missing or conflicting, the residual
  is not computed.
- `finance_metric_pack_input_v1` selects a bundled industry metric vocabulary.
  Packs define required metric ids, value types, and allowed comparison
  directions. They do not contain thresholds or evaluate provider-declared
  pass/fail states.

The packet enforces:

- a cross-sectional screen before a named candidate is selected;
- at least three unrelated screen groups for the de-beta route;
- frozen controls and at least two same-group controls before an
  idiosyncratic de-beta claim can advance;
- supporting facts and counterevidence on every card;
- point-in-time source cutoffs, terminal-risk, dilution, and fully diluted
  valuation gates;
- at most one bounded successor, with no threshold relaxation or continuous
  watch.

It rejects raw provider bodies, private paths, credentials, account or
portfolio material, future-dated evidence, unsupported fields, and malformed
public URLs. It never emits investment advice, a price target, a trade, or an
automatic watch.

## Public-Safe Research Surface

The extension also declares a public-safe `investment-research` presentation
surface. A `finance_research_dashboard_input_v0` packet validates Finance
semantics and maps them to the finance-owned
`decision_research_dashboard_v0` view. The contract keeps beta, cycle,
company-value, and residual-alpha reasoning distinct; requires supporting
evidence, counterevidence, thesis breakers, scenario assumptions, and frozen
event gates; and can publish compact research-artifact pointers with the
evidence references used to produce them. Artifact pointers contain no raw
content or local paths. The view preserves insufficient or rejected conclusions
without allowing free labels or tones to override canonical adjudication, zero
validated alpha, or the unchanged active method, or turn them into an investment
recommendation.

[`examples/research-dashboard.json`](examples/research-dashboard.json) is a
fully synthetic public-safe example. It deliberately reports zero validated
company alpha and an unchanged active method.

After separately installing, enabling, and doctor-validating the extension,
publish a validated local projection with:

```bash
loopx extension publish-projection \
  loopx-finance-value-discovery investment-research \
  --input-json owner-research.json \
  --execute \
  --format json
```

Publication is explicit and local. It validates and stores a read-only
projection bound to the currently active extension revision. A disabled,
doctor-stale, missing, or revision-mismatched extension projection is hidden
from status and Dashboard surfaces. Publishing does not install or enable the
extension, activate or replace a Finance method, spend LoopX quota, consume a
learning queue, create a trade, or place an order.

## Worked Method: How PayPal Surfaced

The historical PayPal exercise started with a fresh de-beta scout, not a
PayPal thesis. The bounded universe covered five unrelated groups: legacy
payments, packaging, agriculture cyclicals, staffing, and freight. Public
filing facts and adjusted price history were used for a first-pass comparison
of growth, margins, cash conversion, balance-sheet resilience, drawdown, and
residual performance.

PayPal surfaced because operating and cash-flow quality remained meaningfully
better than its price-history position suggested. FIS, GPN, and WEX stayed in
the packet as controls. That mattered: the controls separated a possible
PayPal-specific residual from a broad legacy-payments de-rating and kept GPN's
value-trap risk visible instead of averaging the whole group into one bullish
story.

The screen did not produce an investment conclusion. It produced one bounded
successor: review branded checkout and transaction-margin durability, free
cash-flow quality, credit exposure, debt and liquidity, dilution and buybacks,
concentration, competition, regulation, and valuation history. The reusable
lesson is the sequence:

```text
broad blind screen
  -> named candidate
  -> frozen peer controls
  -> idiosyncratic-versus-group-wide test
  -> filing falsification
  -> one successor or close
```

[`examples/paypal-debeta-discovery.json`](examples/paypal-debeta-discovery.json)
encodes that method as an illustrative historical packet. It is not a current
view on PayPal or any control company.

## Install And Run

Install the extension package, then register its manifest with the LoopX
extension runtime:

```bash
python3 -m pip install ./packages/loopx-finance-value-discovery
loopx extension install \
  --manifest packages/loopx-finance-value-discovery/extension.toml \
  --execute \
  --format json
```

Invoke the enabled extension through LoopX's managed runtime:

```bash
loopx extension run loopx-finance-value-discovery \
  --input-json packages/loopx-finance-value-discovery/examples/paypal-debeta-discovery.json \
  --execute \
  --format json
```

The same managed entrypoint accepts a `finance_case_gate_input_v1` object:

```bash
loopx extension run loopx-finance-value-discovery \
  --input-json packages/loopx-finance-value-discovery/examples/finance-case-gates-v1.json \
  --execute \
  --format json
```

Layered attribution and industry packs use the same managed entrypoint:

```bash
loopx extension run loopx-finance-value-discovery \
  --input-json packages/loopx-finance-value-discovery/examples/beta-attribution-v1.json \
  --execute \
  --format json
loopx extension run loopx-finance-value-discovery \
  --input-json packages/loopx-finance-value-discovery/examples/software-metric-pack-v1.json \
  --execute \
  --format json
```

Developers can inspect or replay a frozen evaluation directly:

```bash
loopx-finance-value-discovery evaluate \
  --input-json packages/loopx-finance-value-discovery/examples/finance-case-gates-v1.json
loopx-finance-value-discovery replay \
  --input-json packages/loopx-finance-value-discovery/examples/finance-case-gates-v1.json \
  --expected-json evaluation.json
loopx-finance-value-discovery list-packs
loopx-finance-value-discovery attribute-beta \
  --input-json packages/loopx-finance-value-discovery/examples/beta-attribution-v1.json
loopx-finance-value-discovery evaluate-pack \
  --input-json packages/loopx-finance-value-discovery/examples/software-metric-pack-v1.json
```

The manifest declares no permissions: this workflow is a deterministic reducer
over caller-supplied frozen public evidence. It performs no collection or other
effectful operation. Permissioned Finance work must use a capability or domain
command with an explicit typed authority decision rather than standalone run.

There is no `value-connectors` Finance execution route. The package binary is
a provider implementation and developer-debugging surface, not the supported
management entrypoint. Callers install and invoke this independently versioned
extension through `loopx extension`.

The retired `finance_market_snapshot` value-connector selectors remain only as
machine-readable migration tombstones for upgrades. They point to this
extension but cannot execute it, register a capability, or install an absent
provider implicitly.
