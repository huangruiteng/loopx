# Finance Value Discovery

Status: co-located optional LoopX extension sample.

## Placement

- extension id: `loopx-finance-value-discovery`
- capability registration: none
- placement: `extensions/loopx-finance-value-discovery/`

This optional workflow owns its command and packet contract. LoopX does not
need a provider-neutral finance capability, so installing the extension must
not add `finance-value-discovery` to the capability catalog. The package owns
its dependencies, installation, doctor, enablement, and upgrade lifecycle.

## Contract

The reducer accepts a frozen `finance_value_discovery_input_v0` object and
emits `finance_value_discovery_packet_v0`. It performs no network request. A
separate collector may prepare public evidence cards, but connector output is
input evidence, not accepted truth.

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

The same provider also accepts `finance_market_regime_input_v0` and emits
`finance_market_regime_packet_v0`. This second mode classifies two different
questions without turning either into a trade instruction:

- `precrash`: `no_precrash_signal`, `risk_observation`, or
  `risk_confirmation`;
- `recovery`: `not_in_drawdown`, `unrepaired`, `repair_observation`,
  `repair_confirmation`, or `repair_failed`.

The provider remains a pure reducer. A caller computes the frozen point-in-time
metrics and supplies public source references; the provider validates the exact
market profile and applies the versioned thresholds. It does not fetch prices,
access an account, size a position, or execute an automatic risk action.

## Market Regime Rules v0

The U.S. profile uses SPY as the primary series, QQQ and S&P 500 Equal Weight
relative returns as leadership and participation proxies, HYG as a credit
proxy, and VIX as the volatility input. Its pre-crash layers are:

1. vulnerability: VIX `<= 20` while the primary index is at or above its
   200-day average;
2. leadership or breadth break: QQQ trails by at least 5 percentage points and
   is below its 50-day average, or equal weight trails by at least 3 percentage
   points and is below its 50-day average;
3. credit confirmation: HYG is below its 200-day average with a 20-day return
   of `<= -1%`;
4. trend confirmation: the primary index is below its 200-day average and its
   50-day average has a negative 20-day slope.

The A-share profile uses a CSI 300 ETF as the primary series and CSI 500, CSI
1000, and ChiNext ETFs as participation proxies. Its distinct layers are:

1. crowding or complacency: the primary series is above its 200-day average
   with either a 60-day return of `>= 12%` or 20-day turnover at least `1.25x`
   its 120-day average;
2. leadership or breadth break: the three participation proxies trail by at
   least 4 percentage points on average and at least two are below their
   50-day averages;
3. turnover or leverage unwind: turnover falls from a `>= 1.25x` peak to
   `<= 0.9x` while the primary series has a negative 20-day return;
4. trend confirmation: the primary series is below its 200-day average and its
   50-day average has a negative 20-day slope.

Two pre-crash layers produce a research observation. Confirmation requires at
least three layers and must include credit/trend in the U.S. or turnover/trend
in A shares. Historical blind tests show why the distinction matters. The
rules failed to retain useful precision in the post-2010 U.S. sample and the
short A-share ETF sample, so packets explicitly label them
`research_only_failed_recent_out_of_sample`. They are structured risk-review
inputs, not validated crash predictors, and confirmation can arrive after a
decline has begun.

Recovery is evaluated only after the current drawdown episode has reached
`-15%` in the U.S. or `-18%` in A shares. Eligibility uses the episode's
anchored trough rather than today's improving drawdown, so a valid repair does
not disappear as price rebounds. A rebound must persist, reclaim short trends,
broaden in participation, and show market-specific stress repair. At least two
layers, including rebound persistence, create an observation. Confirmation
needs rebound persistence, the short-trend reclaim, at least one participation
or stress layer, and a total score of at least three. A new low, renewed stress,
or trend re-loss overrides positive layers as `repair_failed`. A one-day
rebound can never qualify. Historical recovery results are marked as promising
but small-sample for the U.S. and insufficient small-sample for A shares.

The ETF and price-based inputs are intentionally described as proxies. HYG is
not an excess-bond-premium series; ETF turnover is not exchange margin balance;
and relative returns are not full advance-decline breadth. Those limitations
remain visible in every packet.

It rejects raw provider bodies, private paths, credentials, account or
portfolio material, future-dated evidence, unsupported fields, and malformed
public URLs. It never emits investment advice, a price target, a trade, or an
automatic watch.

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
python3 -m pip install ./extensions/loopx-finance-value-discovery
loopx extension install \
  --manifest extensions/loopx-finance-value-discovery/extension.toml \
  --execute \
  --format json
```

Invoke the enabled extension through LoopX's managed runtime:

```bash
loopx extension run loopx-finance-value-discovery \
  --input-json extensions/loopx-finance-value-discovery/examples/paypal-debeta-discovery.json \
  --execute \
  --format json
```

Classify one frozen market snapshot through the same managed runtime:

```bash
loopx extension run loopx-finance-value-discovery \
  --input-json extensions/loopx-finance-value-discovery/examples/us-market-regime-2026-07-20.json \
  --execute \
  --format json
```

For package-level debugging only, the direct command is:

```bash
loopx-finance-value-discovery market-signals \
  --input-json extensions/loopx-finance-value-discovery/examples/a-share-market-regime-2026-07-21.json \
  --format markdown
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
