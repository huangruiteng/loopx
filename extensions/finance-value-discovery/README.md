# Finance Value Discovery

Status: co-located optional LoopX extension sample.

## Placement

- capability id: `finance-value-discovery`
- provider id: `loopx-finance-value-discovery`
- origin: `extension`
- placement: `extensions/finance-value-discovery/`

The caller-visible outcome is a finite, falsifiable public-finance research
packet. The implementation has its own package, dependencies, installation,
doctor, enablement, and upgrade lifecycle, so it is extension-delivered rather
than a built-in `loopx/capabilities/` implementation. `value-connectors`
retains only a compatibility delegate during migration.

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

Install the provider package, then register its manifest with the LoopX
extension runtime:

```bash
python3 -m pip install ./extensions/finance-value-discovery
loopx extension install \
  --manifest extensions/finance-value-discovery/extension.toml \
  --execute \
  --format json
```

Run the provider directly:

```bash
loopx-finance-value-discovery reduce \
  --input-json extensions/finance-value-discovery/examples/paypal-debeta-discovery.json \
  --format json
```

The migration compatibility route resolves the installed, enabled,
doctor-ready provider by capability and protocol:

```bash
loopx value-connectors finance-discovery \
  --input-json extensions/finance-value-discovery/examples/paypal-debeta-discovery.json \
  --format json
```
