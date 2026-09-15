"""Semantic counterexamples for the bounded producer observation relation."""
from __future__ import annotations

import pytest

from loopx.semantics.inventory import SourceFile
from loopx.semantics.python_production import scan_python_production

OWNER = 'loopx/quota/owner.py::Action'
ENUMS = {OWNER: {'RUN': 'run', 'WAIT': 'wait'}}


def scan(text, *, returns=(), path='loopx/quota/client.py'):
    return scan_python_production(SourceFile(path, '.py', text), field='action', enums=ENUMS,
                                  return_functions=frozenset(returns))


def known(rows):
    return set().union(*(r.values for r in rows))


def test_owner_definition_does_not_produce_values():
    assert known(scan('class Action:\n RUN = "run"\n WAIT = "wait"\n', path=OWNER.split('::')[0])) == set()


def test_aliased_import_enum_return_and_keyword_produce_values():
    rows = scan('from .owner import Action as A\ndef emit():\n p = Packet(action=A.RUN.value)\n return A.WAIT\n')
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
    rows = scan('def first():\n return {"action": "run"}\ndef second():\n return Packet(action="wait")\n')
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
