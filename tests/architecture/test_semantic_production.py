"""Guard the producer/owner distinction using independent finite counterexamples."""
from __future__ import annotations

import pytest

from loopx.semantics.production import collect_production, validate_production
from loopx.semantics.python_production import Production
from loopx.semantics.inventory import SourceFile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = 'loopx/control_plane/quota/probe.py::emit'


def vocabulary():
    return {'values': ['run', 'wait'], 'producers': [SITE], 'owners': {'python': None},
            'literal_scan': {'field': 'action'}}


def row(value, *, site=SITE, unresolved=False):
    return Production(site, 1, 'return', frozenset([value]) if value else frozenset(), unresolved)


def test_owner_values_never_satisfy_production_liveness():
    with pytest.raises(ValueError, match='no observed producer'):
        validate_production('action', vocabulary(), [row('run')])


def test_undefined_producer_value_is_rejected():
    with pytest.raises(ValueError, match='unregistered values'):
        validate_production('action', vocabulary(), [row('run'), row('typo')])


def test_registering_an_unrelated_function_does_not_cover_a_writer():
    with pytest.raises(ValueError, match='undeclared producer sites'):
        validate_production('action', vocabulary(), [row('run'), row('wait', site=SITE.replace('emit', 'hidden'))])


def test_dynamic_path_remains_visible_and_cannot_supply_missing_value():
    with pytest.raises(ValueError, match='no observed producer'):
        validate_production('action', vocabulary(), [row('run'), row(None, unresolved=True)])
    unknown = validate_production('action', vocabulary(), [row('run'), row('wait'), row(None, unresolved=True)])
    assert unknown == [SITE + ':1']


def test_compatibility_values_must_have_no_observed_production():
    v = vocabulary()
    v['compatibility_only'] = {'wait': {'reason': 'Old reader', 'retirement': 'M1'}}
    assert validate_production('action', v, [row('run')]) == []
    with pytest.raises(ValueError, match='compatibility-only values are produced'):
        validate_production('action', v, [row('run'), row('wait')])


@pytest.mark.parametrize('source, expected', [
    ("function emit() { return {action: flag === 'condition' ? 'run' : 'wait'}; }", {'run', 'wait'}),
    ("function emit() { output['action'] = 'run'; output.action = 'wait'; }", {'run', 'wait'}),
    ("function read() { if (p.action === 'run') console.log('action'); }", set()),
    ("// action: 'comment'\nconst example = `action: 'example'`;", set()),
])
def test_typescript_parser_observes_results_not_context(source, expected):
    rows = collect_production(ROOT, vocabulary(), [SourceFile('loopx/control_plane/quota/probe.ts', '.ts', source)])
    assert set().union(*(r.values for r in rows)) == expected


def test_declared_return_is_scanned_in_real_python_syntax():
    v = vocabulary()
    v['return_producers'] = [SITE]
    rows = collect_production(ROOT, v, [SourceFile(SITE.split('::')[0], '.py', 'def emit():\n return "unregistered"\n')])
    with pytest.raises(ValueError, match='unregistered'):
        validate_production('action', v, rows)


@pytest.mark.parametrize('vocabulary_name, module, original', [
    ('turn_route', 'loopx/control_plane/turn_driver/driver.py', 'return LoopXTurnRoute.CONTRACT_ERROR'),
    ('loop_disposition', 'loopx/control_plane/turn_driver/loop_controller.py', 'LoopXTurnRoute.READY_FOR_HOST: LoopDisposition.RUN_NOW'),
])
def test_real_return_producer_rejects_an_unregistered_result(vocabulary_name, module, original):
    import json
    from loopx.semantics.inventory import load_sources
    v = json.loads((ROOT / 'loopx/semantics/vocabulary_v0.json').read_text())['vocabularies'][vocabulary_name]
    sources = load_sources(ROOT)
    replacement = 'return "unknown_action"' if vocabulary_name == 'turn_route' else 'LoopXTurnRoute.READY_FOR_HOST: "unknown_action"'
    found = False
    mutated = []
    for source in sources:
        if source.path == module:
            assert original in source.text
            source = SourceFile(source.path, source.suffix, source.text.replace(original, replacement, 1))
            found = True
        mutated.append(source)
    assert found
    with pytest.raises(ValueError, match='producer writes unregistered values'):
        validate_production(vocabulary_name, v, collect_production(ROOT, v, mutated))


def test_real_turn_decoder_supplies_typed_input_witnesses():
    from loopx.semantics.production import probe_turn_result_input_domain
    values = ['validated_progress', 'validated_completion', 'repair_required',
              'replan_required', 'user_action_required', 'wait', 'iteration_failed',
              'host_failure', 'validation_failed', 'writeback_failed',
              'quota_spend_failed', 'terminal_closeout_failed']
    v = {'values': values, 'input_producer': 'loopx/control_plane/turn_driver/transaction.py::_result_kind'}
    rows = probe_turn_result_input_domain(v)
    assert {r.form for r in rows} == {'input_witness'}
    assert set().union(*(r.values for r in rows)) == set(values)
    assert all(not r.unresolved for r in rows)


@pytest.mark.parametrize('defect', ['constant_result', 'untyped_result', 'unknown_admitted'])
def test_input_witness_probe_rejects_decoder_contract_regressions(monkeypatch, defect):
    from types import SimpleNamespace
    from loopx.control_plane.turn_driver import transaction
    from loopx.semantics.production import probe_turn_result_input_domain
    original = transaction._result_kind

    def defective(value, errors):
        if defect == 'constant_result':
            return transaction.LoopXTurnResultKind.WAIT
        if defect == 'untyped_result':
            return SimpleNamespace(value=value)
        if value == 'unknown_result_kind':
            return transaction.LoopXTurnResultKind.WAIT
        return original(value, errors)

    monkeypatch.setattr(transaction, '_result_kind', defective)
    v = {'values': ['repair_required'], 'input_producer': 'loopx/control_plane/turn_driver/transaction.py::_result_kind'}
    with pytest.raises(ValueError, match='decoder'):
        probe_turn_result_input_domain(v)


def test_legacy_lease_values_stay_visible_without_claiming_production():
    import json
    from loopx.semantics.inventory import load_sources
    v = json.loads((ROOT / 'loopx/semantics/vocabulary_v0.json').read_text())['vocabularies']['lease_action']
    assert v['status'] == 'legacy'
    assert v['producers'] == []
    assert set(v['compatibility_only']) == {'acquire', 'renew', 'transfer', 'release'}
    rows = collect_production(ROOT, v, load_sources(ROOT))
    assert not any(r.values for r in rows)
    assert validate_production('lease_action', v, rows) == []


def test_new_lease_producer_invalidates_compatibility_only_claim():
    import json
    from loopx.semantics.inventory import load_sources
    v = json.loads((ROOT / 'loopx/semantics/vocabulary_v0.json').read_text())['vocabularies']['lease_action']
    sources = load_sources(ROOT) + [SourceFile('loopx/control_plane/coordination/new_writer.py', '.py',
        'from .authority_core import LeaseAction\ndef emit():\n return LeaseAction.ACQUIRE\n')]
    with pytest.raises(ValueError, match='compatibility-only values are produced'):
        validate_production('lease_action', v, collect_production(ROOT, v, sources))


def test_typescript_syntax_failure_reports_only_source_location():
    source = SourceFile('loopx/control_plane/quota/broken.ts', '.ts', 'const secret = "fixture-only";\nfunction invalid( {')
    with pytest.raises(ValueError, match=r'broken.ts:2: invalid TypeScript source') as error:
        collect_production(ROOT, vocabulary(), [source])
    assert 'fixture-only' not in str(error.value)
