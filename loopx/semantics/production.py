"""Collect and check bounded semantic production evidence for repository CI."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any

from .inventory import SourceFile
from .python_production import Production, enum_members, scan_python_production


# This source boundary is code owned. It is not adjustable through registry data.
PRODUCER_ROOTS = (
    'loopx/cli_commands', 'loopx/control_plane/agents',
    'loopx/control_plane/quota', 'loopx/control_plane/todos', 'loopx/control_plane/coordination',
    'loopx/control_plane/turn_driver', 'loopx/control_plane/work_items',
)


def collect_production(root: Path, vocabulary: dict[str, Any], sources: list[SourceFile]) -> list[Production]:
    by_path = {s.path: s for s in sources}
    owner = vocabulary['owners'].get('python')
    enums = {}
    if owner:
        module, symbol = owner.split('::')
        if module not in by_path:
            raise ValueError(f'producer owner must be a tracked source: {owner}')
        enums[owner] = enum_members(by_path[module], symbol)
    field = vocabulary.get('literal_scan', {}).get('field')
    returns = vocabulary.get('return_producers', [])
    selected = [s for s in sources if any(s.path.startswith(p + '/') for p in PRODUCER_ROOTS)]
    rows = []
    for source in selected:
        if source.suffix == '.py':
            names = frozenset(site.split('::')[1] for site in returns if site.split('::')[0] == source.path)
            rows.extend(scan_python_production(source, field=field, enums=enums, return_functions=names))
    ts_sources = [s for s in selected if s.suffix == '.ts']
    if ts_sources and field:
        completed = subprocess.run(
            ['node', str(root / 'scripts/semantic_production_scan.mjs')],
            input=json.dumps({'field': field, 'sources': [{'path': s.path, 'text': s.text} for s in ts_sources],
                              'return_functions': returns}),
            capture_output=True, text=True, encoding='utf-8', timeout=60, check=False,
        )
        if completed.returncode:
            # Accept only a bounded location from the parser, never echo source
            # text or arbitrary subprocess stderr into public diagnostics.
            try:
                failure = json.loads(completed.stdout)
            except json.JSONDecodeError:
                failure = None
            error = failure.get('error') if isinstance(failure, dict) else None
            if (isinstance(error, dict) and error.get('code') == 'typescript_syntax'
                    and error.get('path') in {s.path for s in ts_sources}
                    and isinstance(error.get('line'), int) and error['line'] > 0):
                raise ValueError(f"{error['path']}:{error['line']}: invalid TypeScript source; repair syntax before semantic scanning")
            raise ValueError('TypeScript production parser failed; run npm ci --ignore-scripts and check the Node runtime')
        rows.extend(Production(r['site'], r['line'], r['form'], frozenset(r['values']), r['unresolved'])
                    for r in json.loads(completed.stdout))
    return rows


def validate_production(name: str, vocabulary: dict[str, Any], rows: list[Production]) -> list[str]:
    """F1/F2 checks on observed results; owner members do not establish liveness.

    Unresolved sites are returned explicitly. They do not supply any missing
    value evidence and this function does not claim whole-program closedness.
    """
    observed = set().union(*(row.values for row in rows))
    expected = set(vocabulary['values'])
    unregistered = observed - expected
    if unregistered:
        sites = sorted({f'{r.site}:{r.line}' for r in rows if r.values & unregistered})
        raise ValueError(f'{name}: producer writes unregistered values {sorted(unregistered)} at {sites}')
    compatibility = set(vocabulary.get('compatibility_only', {}))
    if compatibility - expected:
        raise ValueError(f'{name}: compatibility-only values must be registered')
    if compatibility & observed:
        raise ValueError(f'{name}: compatibility-only values are produced: {sorted(compatibility & observed)}')
    missing = expected - observed - compatibility
    if missing:
        raise ValueError(f'{name}: values have no observed producer: {sorted(missing)}; owner definition is not production')
    producers = vocabulary.get('producers', [])
    declared = set(producers)
    if len(declared) != len(producers):
        raise ValueError(f'{name}: producer sites repeat')
    returns = set(vocabulary.get('return_producers', []))
    if not returns <= declared:
        raise ValueError(f'{name}: return producers must also be registered producers')
    stale = sorted(declared - {row.site for row in rows})
    if stale:
        raise ValueError(f'{name}: producer sites have no observed write or return: {stale}')
    undeclared = sorted({row.site for row in rows if row.values and row.site not in declared})
    if undeclared:
        raise ValueError(f'{name}: undeclared producer sites: {undeclared}')
    return sorted({f'{row.site}:{row.line}' for row in rows if row.unresolved})


def probe_turn_result_input_domain(vocabulary: dict[str, Any]) -> list[Production]:
    """Witness this real decoder's finite output domain, not the host's traces.

    A successful call is evidence that the production function can emit a value
    for a legal input. Merely enumerating the owner is not such evidence. The
    callable is fixed in code; registry data cannot select arbitrary imports.
    """
    from loopx.control_plane.turn_driver.transaction import LoopXTurnResultKind, _result_kind

    site = 'loopx/control_plane/turn_driver/transaction.py::_result_kind'
    if vocabulary.get('input_producer') != site:
        raise ValueError('turn_result_kind: input_producer must name the anchored decoder')
    rows = []
    for value in vocabulary['values']:
        errors: list[str] = []
        actual = _result_kind(value, errors)
        if errors or not isinstance(actual, LoopXTurnResultKind) or actual.value != value:
            raise ValueError(f'turn_result_kind: decoder does not produce registered input {value}')
        rows.append(Production(site, _result_kind.__code__.co_firstlineno, 'input_witness', frozenset({actual.value}), False))
    for invalid in (None, '', 'unknown_result_kind', 3, [], {}):
        errors = []
        actual = _result_kind(invalid, errors)
        if actual is not None or not errors:
            raise ValueError('turn_result_kind: decoder accepted an invalid input probe')
    return rows
