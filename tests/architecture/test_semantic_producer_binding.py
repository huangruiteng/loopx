"""The producer scan's residue stays unresolved; it never becomes a guess.

Track B item B2 of #4447 asks for *bounded* producer identification: dynamic,
aliased, external and unprovable paths must stay explicitly unresolved. A
confident wrong answer is the worst failure this gate can produce, because a
reviewer reads "fully resolved" as "these are all the values this site can
emit". Every construct below was reported as fully resolved by a local
abstract-interpretation attempt that this slice removed; each must now come
back unresolved, carrying the blocker label that says why.

The blocker labels themselves are what B2 keeps: a reason a reviewer can act on
in place of one opaque bucket. A label narrows nothing -- it only names the
obstacle -- so these tests assert the reason *and* that the site stayed unknown.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from loopx.semantics.inventory import SourceFile
from loopx.semantics.production import collect_production
from loopx.semantics.python_production import scan_python_production

ROOT = Path(__file__).resolve().parents[2]
OWNER = 'loopx/quota/owner.py::Action'
ENUMS = {OWNER: {'RUN': 'run', 'WAIT': 'wait'}}
CONSUMER = 'loopx/quota/client.py'
TS_CONSUMER = 'loopx/control_plane/quota/probe.ts'


def scan(text, *, returns=(), paths=None, calls=None, field='action', enums=ENUMS):
    return scan_python_production(SourceFile(CONSUMER, '.py', text), field=field, enums=enums,
                                  return_functions=frozenset(returns), return_paths=paths,
                                  call_arguments=calls)


def known(rows):
    return set().union(*(row.values for row in rows if row.form != 'keyword_unproved'))


def blockers(rows):
    return {row.blocker for row in rows if row.unresolved}


def only(rows, form):
    return [row for row in rows if row.form == form]


def ts_vocabulary():
    return {'values': ['run', 'wait'], 'producers': ['loopx/control_plane/quota/probe.py::emit'],
            'owners': {'python': None}, 'literal_scan': {'field': 'action'}}


def ts_scan(text):
    return collect_production(ROOT, ts_vocabulary(), [SourceFile(TS_CONSUMER, '.ts', text)])


# --- five reproductions of confidently wrong answers --------------------------
#
# Each case below has a value the scan cannot see. Reporting the values it *can*
# see as the complete set would be the false verdict; the honest answer is that
# the complete set is unknown.


def test_a_loop_carried_write_is_not_the_first_iteration_alone():
    """The second iteration emits ``drop``; only the first write precedes the read.

    Ordering a local's writes by source position is sound only in straight-line
    code. Inside a loop the textually *later* write reaches the read on the next
    iteration, so 'the writes above this line' is not the set of possible values.
    """
    rows = only(scan('def emit(rows):\n choice = "run"\n for row in rows:\n'
                     '  packet = {"action": choice}\n  choice = "drop"\n return packet\n'), 'dict')
    assert rows and all(row.unresolved for row in rows)
    assert blockers(rows) == {'unstable_local'}
    assert known(rows) == set()


def test_a_negative_index_write_is_not_a_write_to_a_different_key():
    """``codes[-1]`` and ``codes[0]`` are the same element of a one-item list."""
    rows = only(scan('def emit():\n codes = ["run"]\n codes[-1] = "drop"\n'
                     ' return {"action": codes[0]}\n'), 'dict')
    assert rows and all(row.unresolved for row in rows)
    assert blockers(rows) == {'unstable_local'}
    assert 'run' not in known(rows)


def test_a_dict_mutated_after_construction_is_not_read_from_its_initializer():
    """A ``**`` spread of a mutated local must not replay the stale literal."""
    rows = only(scan('def emit():\n overrides = {"action": "run"}\n'
                     ' overrides["action"] = "drop"\n return {**overrides}\n',
                     returns=['emit'], paths={'emit': ('action',)}), 'return')
    assert rows and all(row.unresolved for row in rows)
    assert blockers(rows) == {'dynamic_key'}
    assert known(rows) == set()


def test_a_helper_rebound_through_global_is_not_the_module_level_function():
    """``install()`` replaces ``pick``; the call site cannot be read off the ``def``."""
    rows = only(scan('def pick():\n return "run"\n'
                     'def install():\n global pick\n pick = other\n'
                     'def emit():\n return {"action": pick()}\n'), 'dict')
    assert rows and all(row.unresolved for row in rows)
    assert blockers(rows) == {'call_result'}
    assert known(rows) == set()


def test_a_typescript_parameter_shadowing_string_is_not_the_builtin_conversion():
    """``String`` here is a caller-supplied function that can return anything."""
    rows = ts_scan('function emit(String) {\n  return {action: String("run")};\n}\n')
    assert rows and all(row.unresolved for row in rows)
    assert blockers(rows) == {'call_result'}
    assert set().union(*(row.values for row in rows)) == set()


# --- the residue is labelled, and a label is not a narrowing -------------------


@pytest.mark.parametrize('text, reason', [
    # An attribute of an object this scan never resolved.
    ('function emit(decision) {\n  return {action: decision.effective_action};\n}\n', 'attribute_read'),
    # A fallback is not the obstacle; the operand that could not be read is.
    ('function emit(decision) {\n  return {action: decision.effective_action ?? ""};\n}\n', 'attribute_read'),
    # A value handed back by a call.
    ('function emit(input) {\n  return {action: project(input)};\n}\n', 'call_result'),
    ('function emit(input) {\n  return {action: await project(input)};\n}\n', 'call_result'),
    # A bare local name.
    ('function emit(choice) {\n  return {action: choice};\n}\n', 'unstable_local'),
])
def test_typescript_unresolved_writes_name_their_own_reason(text, reason):
    """B2 keeps the taxonomy: one opaque bucket told a reviewer nothing."""
    rows = ts_scan(text)
    assert rows and all(row.unresolved and not row.values for row in rows)
    assert blockers(rows) == {reason}


def test_typescript_dynamic_remains_only_as_the_unclassifiable_fallback():
    rows = ts_scan('function emit(a, b) {\n  return {action: a + b};\n}\n')
    assert blockers(rows) == {'typescript_dynamic'}


def test_python_and_typescript_report_the_same_labels_for_the_same_shape():
    shape = 'attribute_read'
    python = scan('def emit(decision):\n return {"action": decision.effective_action}\n')
    typescript = ts_scan('function emit(decision) {\n  return {action: decision.effective_action};\n}\n')
    assert blockers(python) == blockers(typescript) == {shape}


def test_an_unbound_site_is_unresolved_and_never_silently_dropped():
    """No recognized producer means unresolved; it never means dead."""
    rows = scan('def emit(payload):\n return {"action": payload.get("action")}\n')
    assert len(rows) == 1
    assert rows[0].unresolved and rows[0].blocker == 'call_result'
    assert rows[0].values == frozenset()


# --- argument_name_only: resolved values, and still correctly unresolved -------


def test_a_field_named_keyword_stays_unproved_even_when_its_value_is_known():
    """A resolved expression is not a resolved *role*, and the gate wants the role.

    The scan can read this argument perfectly well -- it is an owner member. The
    site stays unresolved because the callee is not a reviewed output builder:
    a helper that takes a field-named keyword is at least as likely to read the
    field as to emit it. Counting any field-named keyword as production would
    make the obligation tautological, which Section 5 of the RFC forbids.

    Narrowing this bucket therefore needs a registry ``call_producers`` entry
    naming the builder -- a data edit a reviewer sees and approves -- and not a
    cleverer scanner. That is why these sites keep a fully resolved value set
    alongside ``unresolved``; the pair is the evidence for the registry edit.
    """
    rows = scan('from .owner import Action\ndef emit():\n return record(action=Action.RUN.value)\n')
    assert len(rows) == 1
    assert rows[0].form == 'keyword_unproved'
    assert rows[0].unresolved and rows[0].blocker == 'argument_name_only'
    assert rows[0].values == frozenset({'run'})


def test_a_declared_output_builder_is_what_turns_that_value_into_production():
    rows = scan('from .owner import Action\ndef emit():\n return record(action=Action.RUN.value)\n',
                calls={f'{CONSUMER}::record': {'action': 0}})
    assert [row.form for row in rows] == ['call_argument']
    assert known(rows) == {'run'} and not rows[0].unresolved
