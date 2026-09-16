"""Semantic counterexamples for the bounded producer observation relation."""
from __future__ import annotations

import pytest

from loopx.semantics.inventory import SourceFile
from loopx.semantics.python_production import scan_python_production

OWNER = 'loopx/quota/owner.py::Action'
ENUMS = {OWNER: {'RUN': 'run', 'WAIT': 'wait'}}


def scan(text, *, returns=(), path='loopx/quota/client.py', calls=None, paths=None):
    return scan_python_production(SourceFile(path, '.py', text), field='action', enums=ENUMS,
                                  return_functions=frozenset(returns), call_arguments=calls, return_paths=paths)


def known(rows):
    return set().union(*(r.values for r in rows if r.form != 'keyword_unproved'))


def test_owner_definition_does_not_produce_values():
    assert known(scan('class Action:\n RUN = "run"\n WAIT = "wait"\n', path=OWNER.split('::')[0])) == set()


def test_aliased_import_enum_return_and_keyword_produce_values():
    rows = scan('from .owner import Action as A\ndef emit():\n p = Packet(action=A.RUN.value)\n return A.WAIT\n',
                calls={'loopx/quota/client.py::Packet': {'action': 0}})
    assert known(rows) == {'run', 'wait'}
    assert {r.site for r in rows} == {'loopx/quota/client.py::emit'}


def test_local_owner_use_counts_but_definition_does_not():
    rows = scan('class Action:\n RUN = "run"\n WAIT = "wait"\ndef emit():\n return Action.RUN.value\n', path=OWNER.split('::')[0])
    assert known(rows) == {'run'}


def test_comparison_and_read_keys_are_not_production():
    rows = scan('from .owner import Action\ndef read(p):\n if p["action"] == Action.RUN.value:\n  return p.get("action")\n')
    assert known(rows) == set()


def test_registered_return_function_includes_only_its_own_returns():
    rows = scan('def emit(flag):\n def inner():\n  return "inner"\n return "left" if flag == "condition" else "right"\n', returns=['emit'])
    assert known(rows) == {'left', 'right'}
    assert {r.site for r in rows} == {'loopx/quota/client.py::emit'}


def test_single_local_variable_and_reassignment_boundary():
    rows = scan('def emit(flag):\n code = "run" if flag else "wait"\n return code\n', returns=['emit'])
    assert known(rows) == {'run', 'wait'}
    assert not any(r.unresolved for r in rows)
    rows = scan('def emit(flag):\n code = "run"\n if flag:\n  code = dynamic()\n return code\n', returns=['emit'])
    assert known(rows) == set()
    assert rows[0].unresolved


def test_parameter_shadowing_does_not_borrow_owner_values():
    rows = scan('from .owner import Action\ndef emit(Action):\n return Action.RUN.value\n', returns=['emit'])
    assert known(rows) == set()
    assert rows[0].unresolved


def test_same_name_import_from_wrong_module_is_unknown():
    rows = scan('from .unrelated import Action\ndef emit():\n return Action.RUN.value\n', returns=['emit'])
    assert known(rows) == set()
    assert rows[0].unresolved


def test_unknown_member_fails_with_location():
    with pytest.raises(ValueError, match=r'client.py:3: unknown owner member MISSING'):
        scan('from .owner import Action\ndef emit():\n return Action.MISSING.value\n')


def test_unresolved_result_preserves_conditional_literal_evidence():
    rows = scan('def emit(flag):\n return "run" if flag else dynamic()\n', returns=['emit'])
    assert known(rows) == {'run'}
    assert rows[0].unresolved


def test_field_write_sites_are_attributed_to_distinct_functions():
    rows = scan('def first():\n return {"action": "run"}\ndef second():\n return Packet(action="wait")\n',
                calls={'loopx/quota/client.py::Packet': {'action': 0}})
    assert {(r.site, tuple(r.values)) for r in rows} == {
        ('loopx/quota/client.py::first', ('run',)),
        ('loopx/quota/client.py::second', ('wait',)),
    }


def test_local_import_shadowing_does_not_borrow_owner_values():
    rows = scan('from .owner import Action\ndef emit():\n from .unrelated import Action\n return Action.RUN.value\n', returns=['emit'])
    assert known(rows) == set()
    assert rows[0].unresolved


def test_assignment_after_return_is_not_a_variable_definition():
    rows = scan('def emit():\n return code\n code = "run"\n', returns=['emit'])
    assert known(rows) == set()
    assert rows[0].unresolved


def test_module_rebind_of_builtin_str_is_unknown():
    rows = scan('str = custom\ndef emit():\n return str("run")\n', returns=['emit'])
    assert known(rows) == set()
    assert rows[0].unresolved


def test_enum_used_only_as_mapping_key_does_not_produce_that_enum():
    rows = scan('from .owner import Action\ndef explain(value):\n reasons = {Action.RUN: "text"}\n return reasons[value]\n')
    assert known(rows) == set()


def test_enum_comparison_inside_result_packet_does_not_produce_operand():
    rows = scan('from .owner import Action\ndef explain(value):\n packet = {"ok": value == Action.RUN}\n return packet\n')
    assert known(rows) == set()


def test_dictionary_lookup_result_includes_values_not_keys():
    rows = scan('from .owner import Action\ndef route(value):\n return {"x": Action.RUN, "y": Action.WAIT}[value]\n', returns=['route'])
    assert known(rows) == {'run', 'wait'}
    assert any(row.unresolved for row in rows)


def test_local_enum_dispatch_table_is_a_consumer_not_a_producer():
    from loopx.semantics.production import validate_production

    rows = scan('from .owner import Action\ndef is_quiet(packet):\n choices = (Action.RUN.value, Action.WAIT.value)\n return packet.get("action") in choices\n')
    assert known(rows) == set()
    with pytest.raises(ValueError, match='no observed producer'):
        validate_production('action', {'values': ['run', 'wait'], 'producers': []}, rows)


def test_local_enum_container_can_feed_a_real_scalar_write():
    rows = scan('from .owner import Action\ndef emit():\n choices = (Action.RUN.value, Action.WAIT.value)\n return {"action": choices[1]}\n')
    assert known(rows) == {'wait'}
    assert {r.form for r in rows} == {'dict'}


@pytest.mark.parametrize('container', [
    '(Action.RUN.value, Action.WAIT.value)',
    '{Action.RUN.value, Action.WAIT.value}',
    '{"first": Action.RUN.value, "second": Action.WAIT.value}',
])
@pytest.mark.parametrize('use', ['return predicate(choices)', 'predicate(allowed=choices)',
                                 'return packet.get("action") in choices'])
def test_enum_containers_only_used_by_predicates_cannot_establish_liveness(container, use):
    rows = scan(f'from .owner import Action\ndef consume(packet):\n choices = {container}\n {use}\n')
    assert known(rows) == set()


@pytest.mark.parametrize('expression', [
    'predicate((Action.RUN, Action.WAIT))',
    'predicate(allowed={Action.RUN, Action.WAIT})',
    'predicate(allowed={"x": Action.RUN})',
    'predicate(Action.RUN)',
    'predicate(action=(Action.RUN, Action.WAIT))',
])
def test_arbitrary_calls_are_not_enum_output_builders(expression):
    assert known(scan(f'from .owner import Action\ndef consume():\n return {expression}\n')) == set()


@pytest.mark.parametrize('container,index,expected', [
    ('(Action.RUN.value, Action.WAIT.value)', '1', {'wait'}),
    ('[Action.RUN.value, Action.WAIT.value]', '-1', {'wait'}),
    ('{"first": Action.RUN.value, "second": Action.WAIT.value}', '"first"', {'run'}),
])
def test_local_container_aliases_resolve_only_selected_output_elements(container, index, expected):
    rows = scan(f'from .owner import Action\ndef emit():\n choices = {container}\n alias = choices\n return {{"action": alias[{index}]}}\n')
    assert known(rows) == expected
    assert not any(r.unresolved for r in rows)


def test_enum_container_written_as_a_scalar_is_unknown_not_two_produced_actions():
    rows = scan('from .owner import Action\ndef emit():\n choices = (Action.RUN, Action.WAIT)\n return {"action": choices}\n')
    assert known(rows) == set()
    assert rows and all(row.unresolved for row in rows)


def test_returned_tuple_needs_an_explicit_scalar_output_path():
    # Use a neutral local name: an assignment named `action` is itself one of
    # the scanner's explicitly supported field-write forms.
    text = 'from .owner import Action\ndef emit():\n selected = Action.RUN.value\n return selected, "reason"\n'
    assert known(scan(text)) == set()
    rows = scan(text, returns=['emit'], paths={'emit': (0,)})
    assert known(rows) == {'run'}


def test_returning_allowed_values_does_not_witness_scalar_liveness():
    from loopx.semantics.production import validate_production

    rows = scan('from .owner import Action\ndef allowed():\n return Action.RUN.value, Action.WAIT.value\n')
    assert known(rows) == set()
    with pytest.raises(ValueError, match='no observed producer'):
        validate_production('action', {'values': ['run', 'wait'], 'producers': []}, rows)


def test_field_named_predicate_keywords_cannot_supply_liveness():
    from loopx.semantics.production import validate_production

    rows = scan('from .owner import Action\ndef query():\n return predicate(action=Action.RUN.value) or predicate(action=Action.WAIT.value)\n')
    assert known(rows) == set()
    assert rows and all(row.unresolved for row in rows)
    with pytest.raises(ValueError, match='no observed producer'):
        validate_production('action', {'values': ['run', 'wait'], 'producers': []}, rows)
    # Still retain the literal's closedness evidence when its output role is unknown.
    rows = scan('def query():\n return predicate(action="unregistered")\n')
    with pytest.raises(ValueError, match='unregistered values'):
        validate_production('action', {'values': ['run'], 'producers': []}, rows)


def test_explicit_output_builder_tracks_import_alias_and_only_declared_argument():
    rows = scan('from .owner import Action\nfrom .builder import emit as build\ndef run():\n build(Action.RUN, context=Action.WAIT)\n',
                calls={'loopx/quota/builder.py::emit': {'verdict': 0}})
    assert known(rows) == {'run'}
    assert {r.form for r in rows} == {'call_argument'}


@pytest.mark.parametrize('prefix,parameters,body', [
    ('from .wrong import emit', '', 'emit(Action.RUN)'),
    ('from .builder import emit', 'emit', 'emit(Action.RUN)'),
    ('from .builder import emit\nemit = predicate', '', 'emit(Action.RUN)'),
    ('from .builder import emit', '', 'emit = predicate\n emit(Action.RUN)'),
    ('from .builder import emit', '', 'from .wrong import emit\n emit(Action.RUN)'),
])
def test_wrong_or_shadowed_builder_cannot_borrow_output_evidence(prefix, parameters, body):
    rows = scan(f'from .owner import Action\n{prefix}\ndef run({parameters}):\n {body}\n',
                calls={'loopx/quota/builder.py::emit': {'verdict': 0}})
    assert known(rows) == set()


def test_known_and_unknown_builder_arguments_preserve_closedness_evidence():
    rows = scan('from .builder import emit\ndef run(flag):\n emit("typo" if flag else dynamic())\n',
                calls={'loopx/quota/builder.py::emit': {'verdict': 0}})
    assert known(rows) == {'typo'}
    assert rows[0].unresolved


def test_exhaustive_branch_selection_produces_only_at_output():
    body = ('from .owner import Action\ndef emit(flag):\n'
            ' if flag:\n  choice = Action.RUN\n else:\n  choice = Action.WAIT\n')
    assert known(scan(body + ' return {"action": choice.value}\n')) == {'run', 'wait'}
    assert known(scan(body + ' return predicate(choice)\n')) == set()


def test_declared_return_path_does_not_borrow_sibling_values():
    rows = scan('def emit():\n packet = {"route": {"kind": "run"}, "diagnostic": "not-an-action"}\n return packet\n',
                returns=['emit'], paths={'emit': ('route', 'kind')})
    assert known(rows) == {'run'}
    assert not any(r.unresolved for r in rows)


def test_dynamic_lookup_retains_known_possibilities_and_unknown_boundary():
    rows = scan('from .owner import Action\ndef emit(index):\n choices = (Action.RUN, dynamic())\n return {"action": choices[index]}\n')
    assert known(rows) == {'run'}
    assert rows[0].unresolved


@pytest.mark.parametrize('mutation', ['choices[0] = dynamic()', 'alias[0] = dynamic()',
                                     'choices.clear()', 'predicate(choices)'])
def test_mutated_or_escaped_local_container_does_not_reuse_stale_elements(mutation):
    rows = scan('from .owner import Action\ndef emit():\n choices = [Action.RUN]\n alias = choices\n '
                + mutation + '\n return {"action": alias[0]}\n')
    assert known(rows) == set()
    assert rows and all(row.unresolved for row in rows)


@pytest.mark.parametrize('index', ['99', '"not-an-index"', '1:', 'None'])
def test_non_scalar_or_invalid_literal_lookup_cannot_produce_scalar_action(index):
    rows = scan(f'from .owner import Action\ndef emit():\n choices = (Action.RUN, Action.WAIT)\n return {{"action": choices[{index}]}}\n')
    assert known(rows) == set()
    assert rows[0].unresolved


@pytest.mark.parametrize('value', ['"run"', 'Action.RUN.value'])
def test_value_attribute_requires_an_enum_object_not_a_serialized_string(value):
    rows = scan(f'from .owner import Action\ndef emit():\n choice = {value}\n return {{"action": choice.value}}\n')
    assert known(rows) == set()
    assert rows[0].unresolved
