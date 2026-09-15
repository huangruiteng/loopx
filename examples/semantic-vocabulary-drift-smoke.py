#!/usr/bin/env python3
"""Guard the repository's registered vocabularies against silent drift.

``loopx/semantics/vocabulary_v0.json`` names each kernel and cross-runtime
vocabulary, the exact ``module::Symbol`` allowed to define it, how vocabularies
relate, and the budgets the repository ratchets down. ``inventory_v0.json`` is
the generated map of every closed-set carrier under ``loopx/``. This smoke
checks code against both so a PR that widens a vocabulary, forks a constant,
adds an unmapped carrier, or weakens the registry itself must show that change
in the same diff. It reads tracked sources only and prints no private data.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.semantics.inventory import (  # noqa: E402
    INVENTORY_SCHEMA_VERSION,
    SourceFile,
    build_inventory,
    collect_string_constants,
    load_sources,
    python_facts,
    render_inventory,
    string_constant_definitions,
    typescript_facts,
)

from loopx.semantics.production import (  # noqa: E402
    collect_production, validate_production, probe_turn_result_input_domain,
)
from loopx.semantics.python_production import scan_python_production  # noqa: E402

REGISTRY_PATH = REPO_ROOT / "loopx" / "semantics" / "vocabulary_v0.json"
REGISTRY_SCHEMA_VERSION = "loopx_semantic_vocabulary_v0"
VALUE_SHAPE = re.compile(r"^[a-z][a-z0-9_]*$")
SYMBOL_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
OWNER_SHAPE = re.compile(r"^[A-Za-z0-9_./-]+\.(py|ts)::[A-Za-z_][A-Za-z0-9_]*$")
QUOTED = re.compile(r'''["']([^"']*)["']''')

REGISTRY_KEYS = {
    "schema_version", "rfc", "inventory", "policy", "coverage_floor", "vocabularies", "relations",
    "projections", "schema_versions", "retirement_ledger", "dual_runtime_twins", "inventory_ratchets",
    "formal_model", "scope_declarations",
}
VOCABULARY_KEYS = {"meaning", "tier", "status", "owners", "values"}
VOCABULARY_OPTIONAL_KEYS = {
    "literal_scan",
    "variable_sourced_values",
    "value_notes",
    "deprecated_values",
    "producers",
    "compatibility_only",
    "return_producers",
    "input_producer",
}
TIERS = {"kernel", "cross_runtime", "cross_module"}
STATUSES = {"canonical", "legacy", "merge_candidate"}
FORMAL_MODEL_KEYS = {
    "schema_version", "universes", "roles", "role_hierarchy", "relations", "invariants", "proof_boundary",
    "enforcement_policy",
}
FORMAL_MODEL_SCHEMA_VERSION = "loopx_semantic_formal_model_v0"
FORMAL_UNIVERSE_KEYS = {"vocabularies", "values", "sites", "scopes", "roles"}
FORMAL_ROLES = {"owner", "producer", "consumer", "interpreter", "pass_through"}
FORMAL_RELATIONS = {"defines", "produces", "consumes", "interprets", "passes_through", "projects", "persists"}
FORMAL_INVARIANTS = {
    "F1_producer_closedness",
    "F2_canonical_value_liveness",
    "F3_consumer_domain_closedness",
    "F4_scope_separation",
    "F5_projection_totality",
    "F6_persistence_version_compatibility",
}
FORMAL_ENFORCEMENT = {"m0", "m0_5", "m1", "advisory", "unproved"}
FORMAL_POLICY_KEYS = {"blocking_now", "blocking_next", "advisory", "unproved"}

# Hard ceiling on the registry's own floors and budgets, kept in code rather than
# in the registry so one single-diff edit to ``vocabulary_v0.json`` cannot relax
# the ratchet that guards it. Same anchor pattern as
# ``tests/control_plane/test_m6_quality_gates.py::RFC_MODULE_BUDGETS``: the
# registry value must equal the anchor, so tightening a budget edits this literal
# and the JSON in one diff, and a later PR cannot raise the JSON back toward a stale
# anchor. A `<=` comparison would let every tightening below the anchor be undone
# silently; that is the gap the anchor exists to close.
COVERAGE_ANCHOR = {
    "vocabularies": 26,
    "owner_symbols": 47,
    "literal_scan_fields": 1,
    "projections": 1,
    "relations": 9,
    "schema_versions": 1,
}
COVERAGE_SUFFIX_ANCHOR = (".py", ".ts")
LITERAL_SCAN_ROOTS = ["loopx"]
PRODUCER_VOCABULARY_ANCHOR = {
    "effective_action", "turn_route", "loop_disposition", "agent_scope_frontier_action", "turn_result_kind", "lease_action",
}
RETURN_PRODUCER_ANCHOR = {
    "turn_route": {"loopx/control_plane/turn_driver/driver.py::_typed_route", "loopx/control_plane/turn_driver/loop_controller.py::_envelope_route"},
    "loop_disposition": {"loopx/control_plane/turn_driver/loop_controller.py::_route_to_disposition"},
    "effective_action": {"loopx/control_plane/quota/decision_summary.py::quota_effective_action"},
}
TWIN_ROOT_ANCHOR = "loopx/control_plane"
TWIN_BUDGET_ANCHOR = 43
BUDGET_ANCHOR = {
    "same_runtime_forks": 25,
    "same_runtime_fork_definitions": 58,
    "conflicting_values": 18,
    "conflicting_definitions": 59,
    "schema_version_same_runtime_forks": 7,
    "multi_value_twins": 19,
    "multi_value_forks": 4,
    "multi_value_forks_semantic": 3,
    "multi_value_fork_definitions": 10,
    "same_runtime_forks_semantic": 18,
    "conflicting_values_semantic": 2,
}
# Budgets for the legacy should-run decision fields, anchored the same way so a
# single diff cannot widen a retirement budget to keep a field alive.
RETIREMENT_ANCHOR = {
    "execution_obligation": (20, 1),
    "heartbeat_recommendation": (17, 1),
    "work_lane_contract": (29, 3),
    "external_evidence_observation": (8, 1),
    "goal_boundary": (30, 2),
    "protocol_action_packet": (5, 2),
}
RATCHET_KEYS = (
    "same_runtime_forks",
    "same_runtime_fork_definitions",
    "conflicting_values",
    "conflicting_definitions",
    "schema_version_same_runtime_forks",
    "multi_value_twins",
    "multi_value_forks",
    "multi_value_forks_semantic",
    "multi_value_fork_definitions",
    "same_runtime_forks_semantic",
    "conflicting_values_semantic",
)

# Dispatch forms the literal scan recognises. Fixed here, not in the registry, so
# the registry cannot narrow what the scan sees. ``{f}`` is the field name.
DISPATCH_FORMS = (
    # Python/TypeScript comparisons, including wrapped field reads.
    r"""{f}\b[^\n]*?(?:===|!==|==|!=)\s*["']([^"']*)["']""",
    # Assignment or object/dict key.
    r"""{f}["\'\]\)]*\s*(?::|=|\bis)\s*["']([^"']*)["']""",
    # TypeScript conditional expression.
    r"""{f}\b[^"\n]*?\?\s*["']([^"']*)["']\s*:\s*["']([^"']*)["']""",
    # Membership in an inline collection.
    r"""{f}["\'\]\)]*[^"\n]*?\bin\s*[\(\[\{{]([^\)\]\}}]*)[\)\]\}}]""",
    # Python conditional expression.
    r"""{f}\b[^"\n]*?=\s*["']([^"']*)["']\s+if\b[^"\n]*?\belse\s+["']([^"']*)["']""",
)
MEMBERSHIP_FORM_INDEX = 3


class Drift(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Drift(message)


# --- registry shape -----------------------------------------------------------------


def load_registry() -> dict[str, Any]:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    require(set(registry) == REGISTRY_KEYS, f"registry keys must be exactly {sorted(REGISTRY_KEYS)}")
    require(registry["schema_version"] == REGISTRY_SCHEMA_VERSION, f"registry schema_version must be {REGISTRY_SCHEMA_VERSION}")
    check_formal_model(registry["formal_model"])
    require((REPO_ROOT / registry["rfc"]).is_file(), f"registry must point at an existing RFC: {registry['rfc']}")
    require((REPO_ROOT / registry["inventory"]).is_file(), f"registry must point at an existing inventory: {registry['inventory']}")
    for name, vocabulary in registry["vocabularies"].items():
        require(VALUE_SHAPE.match(name) is not None, f"vocabulary name must be lower snake_case: {name}")
        keys = set(vocabulary)
        require(VOCABULARY_KEYS <= keys <= VOCABULARY_KEYS | VOCABULARY_OPTIONAL_KEYS, f"{name}: unexpected keys {sorted(keys ^ VOCABULARY_KEYS)}")
        require(vocabulary["tier"] in TIERS, f"{name}: tier must be one of {sorted(TIERS)}")
        require(vocabulary["status"] in STATUSES, f"{name}: status must be one of {sorted(STATUSES)}")
        owners = vocabulary["owners"]
        require(set(owners) == {"python", "typescript"}, f"{name}: owners must name python and typescript, each module::Symbol or null")
        for runtime, owner in owners.items():
            if owner is None:
                continue
            require(OWNER_SHAPE.match(owner) is not None, f"{name}: {runtime} owner must be module::Symbol, got {owner!r}")
            require(owner.endswith(".py::" + owner.split("::")[1]) if runtime == "python" else owner.split("::")[0].endswith(".ts"), f"{name}: {runtime} owner has the wrong suffix: {owner}")
            require((REPO_ROOT / owner.split("::")[0]).is_file(), f"{name}: owner module does not exist: {owner}")
        require(any(owners.values()) or "literal_scan" in vocabulary, f"{name}: a vocabulary with no owner symbol must declare a literal_scan")
        values = vocabulary["values"]
        require(isinstance(values, list) and values, f"{name}: values must be a non-empty list")
        require(len(values) == len(set(values)), f"{name}: values repeat")
        malformed = [value for value in values if not VALUE_SHAPE.match(value)]
        require(not malformed, f"{name}: values must be lower snake_case: {malformed}")
        for key in ("value_notes", "variable_sourced_values"):
            extra = set(vocabulary.get(key, {})) - set(values)
            require(not extra, f"{name}: {key} names unregistered values {sorted(extra)}")
        require(set(vocabulary.get("deprecated_values", [])) <= set(values), f"{name}: deprecated_values must be a subset of values")
        producers = vocabulary.get("producers")
        if producers is not None:
            require(isinstance(producers, list), f"{name}: producers must be a list")
            require(bool(producers) or set(vocabulary.get('compatibility_only', {})) == set(values), f"{name}: empty producers require every value to be compatibility-only")
            require(all(isinstance(site, str) and OWNER_SHAPE.match(site) for site in producers), f"{name}: producers must be module::Symbol sites")
        if 'input_producer' in vocabulary:
            require(name == 'turn_result_kind', f"{name}: no executable input producer verifier is implemented")
            require(vocabulary['input_producer'] == 'loopx/control_plane/turn_driver/transaction.py::_result_kind', f"{name}: unrecognised input producer")
        returns = vocabulary.get("return_producers", [])
        require(isinstance(returns, list) and all(isinstance(site, str) and OWNER_SHAPE.match(site) for site in returns), f"{name}: return_producers must be module::Symbol sites")
        require(set(returns) <= set(producers or []), f"{name}: return_producers must also be registered producers")
        compatibility = vocabulary.get("compatibility_only")
        if compatibility is not None:
            require(isinstance(compatibility, dict), f"{name}: compatibility_only must be an object")
            for value, metadata in compatibility.items():
                require(isinstance(metadata, dict) and set(metadata) == {"reason", "retirement"}, f"{name}: compatibility_only.{value} needs reason and retirement")
                require(all(isinstance(item, str) and item.strip() for item in metadata.values()), f"{name}: compatibility_only.{value} metadata must be non-empty text")
        scan = vocabulary.get("literal_scan")
        if scan is not None:
            require(set(scan) == {"field", "roots", "suffixes"}, f"{name}: literal_scan keys must be field, roots, suffixes")
            require(VALUE_SHAPE.match(scan["field"]) is not None, f"{name}: literal_scan.field must be an identifier")
    return registry


def check_formal_model(model: dict[str, Any]) -> None:
    """Validate the formal vocabulary model's finite signature and proof ledger.

    This is deliberately a schema check, not a claim that the current scanner
    proves every property. Each property carries an enforcement stage and the
    proof boundary records what remains unproved.
    """
    require(set(model) == FORMAL_MODEL_KEYS, f"formal_model keys must be exactly {sorted(FORMAL_MODEL_KEYS)}")
    require(model["schema_version"] == FORMAL_MODEL_SCHEMA_VERSION, "formal_model schema_version drift")
    require(set(model["universes"]) == FORMAL_UNIVERSE_KEYS, "formal_model universes must name the declared sets")
    require(set(model["roles"]) == FORMAL_ROLES, "formal_model roles must include the consumer role and its subroles")
    require(model["role_hierarchy"] == {"consumer": ["interpreter", "pass_through"]},
            "formal_model role_hierarchy must classify interpreter and pass_through as consumers")
    require(set(model["relations"]) == FORMAL_RELATIONS, "formal_model relations must be the declared edge kinds")
    invariants = model["invariants"]
    require(isinstance(invariants, list) and {item.get("id") for item in invariants} == FORMAL_INVARIANTS,
            "formal_model invariants must cover exactly F1-F6")
    for item in invariants:
        require(set(item) == {"id", "statement", "enforcement", "evidence"},
                f"formal invariant {item.get('id')} has an invalid shape")
        require(item["enforcement"] in FORMAL_ENFORCEMENT,
                f"formal invariant {item['id']} has unknown enforcement stage")
        require(item["statement"].strip() and item["evidence"].strip(),
                f"formal invariant {item['id']} needs a statement and evidence boundary")
    policy = model["enforcement_policy"]
    require(set(policy) == FORMAL_POLICY_KEYS,
            "formal_model enforcement_policy must separate current, next, advisory, and unproved checks")
    policy_ids = [item_id for ids in policy.values() for item_id in ids]
    require(set(policy_ids) == FORMAL_INVARIANTS and len(policy_ids) == len(set(policy_ids)),
            "formal_model enforcement_policy must partition all invariants exactly once")
    stage_for_policy = {
        "blocking_now": "m0",
        "blocking_next": "m0_5",
        "advisory": "advisory",
        "unproved": "unproved",
    }
    stages = {item["id"]: item["enforcement"] for item in invariants}
    for policy_name, ids in policy.items():
        require(all(stages[item_id] == stage_for_policy[policy_name] for item_id in ids),
                f"formal_model policy lane {policy_name} disagrees with invariant enforcement stage")
    boundary = model["proof_boundary"]
    require(set(boundary) == {"established", "bounded", "unproved"},
            "formal_model proof_boundary must separate established, bounded, and unproved claims")
    for key in boundary:
        require(isinstance(boundary[key], list) and all(isinstance(value, str) and value.strip() for value in boundary[key]),
                f"formal_model proof_boundary.{key} must contain non-empty claim names")


def check_coverage_floor(registry: dict[str, Any]) -> str:
    require(
        registry['vocabularies']['turn_result_kind'].get('input_producer') == 'loopx/control_plane/turn_driver/transaction.py::_result_kind',
        'turn_result_kind: input producer coverage must retain the anchored decoder',
    )
    for name in PRODUCER_VOCABULARY_ANCHOR:
        require("producers" in registry["vocabularies"][name], f"{name}: producer coverage dropped below PRODUCER_VOCABULARY_ANCHOR")
    for name, required in RETURN_PRODUCER_ANCHOR.items():
        actual_returns = set(registry['vocabularies'][name].get('return_producers', []))
        require(required <= actual_returns, f"{name}: return producer coverage dropped below RETURN_PRODUCER_ANCHOR")
    for vocabulary in registry["vocabularies"].values():
        if scan := vocabulary.get("literal_scan"):
            require(scan["roots"] == LITERAL_SCAN_ROOTS, "literal_scan roots must cover loopx")
            require(set(scan["suffixes"]) == set(COVERAGE_SUFFIX_ANCHOR), "literal_scan must cover both Python and TypeScript")
    floor = registry["coverage_floor"]
    actual = {
        "vocabularies": len(registry["vocabularies"]),
        "owner_symbols": sum(1 for v in registry["vocabularies"].values() for o in v["owners"].values() if o),
        "literal_scan_fields": sum(1 for v in registry["vocabularies"].values() if "literal_scan" in v),
        "projections": len(registry["projections"]),
        "relations": sum(len(group) for group in registry["relations"].values()),
        "schema_versions": len(registry["schema_versions"]),
    }
    for key, count in actual.items():
        require(count >= floor[key], f"coverage_floor.{key} is {floor[key]} but the registry now has {count}; coverage may only grow")
    declared_suffixes = {s for v in registry["vocabularies"].values() for s in v.get("literal_scan", {}).get("suffixes", [])}
    require(set(floor["literal_scan_suffixes"]) <= declared_suffixes, f"literal scans must still cover {floor['literal_scan_suffixes']}; declared {sorted(declared_suffixes)}")
    for key, anchored in COVERAGE_ANCHOR.items():
        require(
            floor[key] == anchored,
            f"coverage_floor.{key} is {floor[key]} but COVERAGE_ANCHOR pins {anchored}; "
            "the registry and the anchor move together in one diff (see COVERAGE_ANCHOR in this smoke)",
        )
    for suffix in COVERAGE_SUFFIX_ANCHOR:
        require(suffix in set(floor["literal_scan_suffixes"]), f"coverage_floor.literal_scan_suffixes dropped the anchored suffix {suffix}")
    return "coverage=" + ",".join(f"{key}:{count}/{floor[key]}" for key, count in actual.items())


# --- owners and closed sets -----------------------------------------------------------


def source(path: str) -> SourceFile:
    file = REPO_ROOT / path
    return SourceFile(path=path, suffix=file.suffix, text=file.read_text(encoding="utf-8", errors="replace"))


def owner_values(owner: str) -> list[str]:
    module, symbol = owner.split("::")
    facts = python_facts(source(module)) if module.endswith(".py") else typescript_facts(source(module))
    sections = ("enums", "closed_sets", "literal_aliases") if module.endswith(".py") else ("const_arrays",)
    for section in sections:
        for entry in facts[section]:
            if entry["name"] == symbol:
                return list(entry["values"])
    raise Drift(f"{module} does not define a string enum, closed set, Literal alias, or as-const array named {symbol}")


def assert_closed_set(label: str, actual: list[str], expected: list[str]) -> None:
    require(len(actual) == len(set(actual)), f"{label} repeats a value: {actual}")
    missing = sorted(set(expected) - set(actual))
    unregistered = sorted(set(actual) - set(expected))
    require(not missing and not unregistered, f"{label} drifted from the registry; missing={missing} unregistered={unregistered}")


def check_owned_vocabularies(registry: dict[str, Any], inventory: dict[str, Any]) -> None:
    defined_in: dict[str, set[str]] = {}
    for section in ("python_enums", "python_closed_sets", "python_literal_aliases", "typescript_const_arrays"):
        for entry in inventory[section]:
            defined_in.setdefault(entry["name"], set()).add(entry["module"])
    problems: list[str] = []
    for name, vocabulary in registry["vocabularies"].items():
        owners = [owner for owner in vocabulary["owners"].values() if owner]
        for owner in owners:
            try:
                assert_closed_set(f"{name} owner {owner}", owner_values(owner), vocabulary["values"])
            except Drift as error:
                problems.append(str(error))
        # I1: a registered symbol name is defined only in its owner modules.
        for owner in owners:
            _module, symbol = owner.split("::")
            others = sorted(defined_in.get(symbol, set()) - {o.split("::")[0] for o in owners})
            if others:
                problems.append(f"{name}: {symbol} is also defined in {others}; only the registered owners may define it")
    require(not problems, "owned vocabularies drifted:\n  " + "\n  ".join(problems))


# --- literal scan -------------------------------------------------------------------


def scan_literals(field: str, roots: list[str], suffixes: list[str], sources: list[SourceFile]) -> dict[str, set[str]]:
    observed: dict[str, set[str]] = {}
    forms = [re.compile(form.format(f=re.escape(field))) for form in DISPATCH_FORMS]
    for root in roots:
        for file in sources:
            if file.suffix not in suffixes or not file.path.startswith(root.rstrip("/") + "/"):
                continue
            for index, form in enumerate(forms):
                for match in form.finditer(file.text):
                    tokens = QUOTED.findall(match.group(1)) if index == MEMBERSHIP_FORM_INDEX else list(match.groups())
                    for token in tokens:
                        if token == "":
                            continue  # ``?? ""`` and ``or ""`` clear the field; not a value
                        observed.setdefault(token, set()).add(file.path)
    return observed


def check_literal_vocabularies(registry: dict[str, Any], sources: list[SourceFile]) -> None:
    for name, vocabulary in registry["vocabularies"].items():
        scan = vocabulary.get("literal_scan")
        if not scan:
            continue
        observed = scan_literals(scan["field"], scan["roots"], scan["suffixes"], sources)
        expected = set(vocabulary["values"])
        unregistered = {value: sorted(files) for value, files in observed.items() if value not in expected}
        require(not unregistered, f"{name}: literals not in the registry (register them or use a registered value): {unregistered}")
        variable_sourced = vocabulary.get("variable_sourced_values", {})
        for value, producer in variable_sourced.items():
            text = (REPO_ROOT / producer).read_text(encoding="utf-8", errors="replace")
            require(f'"{value}"' in text, f"{name}: variable-sourced value {value} is no longer produced by {producer}")
        owner_values_seen = {
            value
            for owner in vocabulary["owners"].values()
            if owner
            for value in owner_values(owner)
        }
        unused = sorted(
            expected - set(observed) - set(variable_sourced) - owner_values_seen
        )
        require(not unused, f"{name}: registry lists values no module carries: {unused}")


# --- bounded producer scan ----------------------------------------------------------


def _producer_literals(field: str, source: SourceFile) -> set[str]:
    # Compatibility helper for direct-form mutation fixtures. No enum definitions
    # are supplied, so these tests cannot accidentally count owners as producers.
    if source.suffix != '.py':
        return set()
    rows = scan_python_production(source, field=field, enums={})
    return set().union(*(row.values for row in rows))


def check_producers(registry: dict[str, Any], sources: list[SourceFile]) -> list[str]:
    unknown: list[str] = []
    for name, vocabulary in registry['vocabularies'].items():
        if 'producers' not in vocabulary:
            continue  # Other kernel families retain an explicit M0.5 coverage gap.
        try:
            rows = collect_production(REPO_ROOT, vocabulary, sources)
            if name == 'turn_result_kind':
                rows.extend(probe_turn_result_input_domain(vocabulary))
            unknown.extend(validate_production(name, vocabulary, rows))
        except ValueError as error:
            raise Drift(str(error)) from error
    return sorted(set(unknown))


# --- relations, projections, schema versions ----------------------------------------


def check_relations(registry: dict[str, Any]) -> None:
    vocabularies = registry["vocabularies"]

    def resolve(member: str) -> None:
        vocabulary, _, value = member.partition(".")
        require(vocabulary in vocabularies, f"relation member names unknown vocabulary: {member}")
        require(value in vocabularies[vocabulary]["values"], f"relation member does not resolve: {member}")

    for group in registry["relations"]["same_concept"]:
        require(len(group["members"]) >= 2, f"same_concept {group['concept']} needs two members")
        for member in group["members"]:
            resolve(member)
    for shared in registry["relations"]["shared_field_names"]:
        for slot in shared["slots"]:
            if "vocabulary" in slot:
                require(slot["vocabulary"] in vocabularies, f"shared field slot names unknown vocabulary {slot['vocabulary']}")
            else:
                for value in slot["values"]:
                    resolve(f"{shared['field']}.{value}")
    for subset in registry["relations"]["subsets"]:
        require(subset["superset"] in vocabularies, f"subset {subset['name']} names unknown superset {subset['superset']}")
        superset = set(vocabularies[subset["superset"]]["values"])
        expected = superset - set(subset["excluded"])
        require(set(subset["excluded"]) <= superset, f"subset {subset['name']} excludes values outside {subset['superset']}")
        for owner in subset["owners"].values():
            if owner:
                assert_closed_set(f"subset {subset['name']} owner {owner}", owner_values(owner), sorted(expected))


def check_projections(registry: dict[str, Any]) -> None:
    projection = registry["projections"]["turn_route_to_loop_disposition"]
    from loopx.control_plane.turn_driver.driver import LoopXTurnRoute
    from loopx.control_plane.turn_driver.loop_controller import LoopDisposition, _route_to_disposition

    mapping = projection["mapping"]
    routes = registry["vocabularies"]["turn_route"]["values"]
    require(sorted(mapping) == sorted(routes), "projection must name every turn_route exactly once")
    for route, expected in mapping.items():
        try:
            actual = _route_to_disposition(LoopXTurnRoute(route))
        except KeyError:
            require(expected is None, f"route {route} is rejected by the controller but the registry maps it to {expected}")
            continue
        require(expected is not None, f"route {route} is registered as rejected but projects {actual.value}")
        require(actual is LoopDisposition(expected), f"route {route} projects {actual.value}, registry says {expected}")


def check_schema_version_owners(registry: dict[str, Any], sources: list[SourceFile]) -> None:
    definitions = string_constant_definitions(collect_string_constants(sources))
    for name, entry in registry["schema_versions"].items():
        defining = definitions.get(entry["constant"], [])
        modules = sorted(item["module"] for item in defining)
        require(modules == sorted(entry["owner_modules"]), f"schema version {name} is defined in {modules}; registry owners are {entry['owner_modules']}")
        values = {item["value"] for item in defining}
        require(values == {entry["value"]}, f"schema version {name} carries {sorted(values)}; registry says {entry['value']}")


def check_scope_declarations(registry: dict[str, Any], inventory: dict[str, Any]) -> int:
    """Validate explicit bounded-context exceptions and return semantic fork count.

    The raw inventory remains unchanged. A declaration can remove a known,
    reviewed bounded-context reuse from the semantic budget only when every
    defining module is named explicitly. Spelling or directory proximity never
    infers a scope.
    """
    declarations = registry["scope_declarations"]
    forks = {entry["name"]: entry for entry in inventory["duplicate_definitions"]["multi_value_forks"]}
    for name, declaration in declarations.items():
        require(SYMBOL_NAME.match(name) is not None, f"scope declaration name must be an identifier: {name}")
        require(set(declaration) == {"kind", "contexts"}, f"{name}: scope declaration keys must be kind and contexts")
        require(declaration["kind"] == "bounded_context", f"{name}: only bounded_context is supported")
        require(name in forks, f"{name}: scope declaration does not resolve to a multi-value fork")
        contexts = declaration["contexts"]
        require(isinstance(contexts, list) and contexts, f"{name}: contexts must be a non-empty list")
        context_ids: set[str] = set()
        owner_modules: set[str] = set()
        for context in contexts:
            require(set(context) == {"id", "owner"}, f"{name}: each context must have id and owner")
            context_id = context["id"]
            require(isinstance(context_id, str) and VALUE_SHAPE.match(context_id) is not None,
                    f"{name}: context id must be lower snake_case: {context_id!r}")
            require(context_id not in context_ids, f"{name}: duplicate context id {context_id}")
            context_ids.add(context_id)
            owner = context["owner"]
            require(isinstance(owner, str) and OWNER_SHAPE.match(owner) is not None,
                    f"{name}: context owner must be module::Symbol: {owner!r}")
            module, symbol = owner.split("::")
            require(symbol == name, f"{name}: context owner symbol must be {name}, got {symbol}")
            owner_modules.add(module)
        require(len(owner_modules) == len(contexts), f"{name}: each context must have a distinct owner module")
        defining_modules = {item["module"] for item in forks[name]["definitions"]}
        require(owner_modules == defining_modules,
                f"{name}: contexts must name every defining module exactly once; "
                f"declared={sorted(owner_modules)} actual={sorted(defining_modules)}")
    undeclared = set(forks) - set(declarations)
    return len(undeclared)


# --- ratchets -----------------------------------------------------------------------


def check_retirement_budgets(registry: dict[str, Any], sources: list[SourceFile]) -> list[str]:
    report: list[str] = []
    ledger = registry["retirement_ledger"]["should_run_legacy_decision_fields"]["fields"]
    require(set(ledger) == set(RETIREMENT_ANCHOR), f"retirement ledger fields are {sorted(ledger)}; the anchored set is {sorted(RETIREMENT_ANCHOR)}")
    for field, budgets in ledger.items():
        for suffix, key, anchored in (
            (".py", "python_module_budget", RETIREMENT_ANCHOR[field][0]),
            (".ts", "typescript_module_budget", RETIREMENT_ANCHOR[field][1]),
        ):
            actual = count_identifier_modules(field, suffix, sources)
            require(actual <= budgets[key], f"legacy field {field} grew to {actual} {suffix} modules; budget is {budgets[key]}")
            require(
                budgets[key] == anchored,
                f"legacy field {field} {suffix} budget is {budgets[key]} but RETIREMENT_ANCHOR pins {anchored}; "
                "the registry and the anchor move together in one diff (see RETIREMENT_ANCHOR in this smoke)",
            )
            report.append(f"{field}{suffix}={actual}/{budgets[key]}")
    return report


def count_identifier_modules(field: str, suffix: str, sources: list[SourceFile]) -> int:
    """Count modules containing the standalone field token.

    This is intentionally a conservative lexical metric. It removes the known
    ``goal_boundary_repair`` false positive without claiming to prove that every
    remaining occurrence is a reader or that computed accesses are absent.
    """
    pattern = re.compile(
        rf"(?<![A-Za-z0-9_]){re.escape(field)}(?![A-Za-z0-9_])"
    )
    return sum(
        1
        for file in sources
        if file.suffix == suffix and pattern.search(file.text)
    )


def check_dual_runtime_twins(registry: dict[str, Any]) -> str:
    entry = registry["dual_runtime_twins"]
    require(entry["root"] == TWIN_ROOT_ANCHOR, "dual_runtime_twins root differs from TWIN_ROOT_ANCHOR")
    require(entry["module_budget"] == TWIN_BUDGET_ANCHOR, "dual_runtime_twins budget differs from TWIN_BUDGET_ANCHOR")
    paths = {file.path for file in load_sources(REPO_ROOT, entry["root"])}
    twins = sorted(path for path in paths if path.endswith(".py") and not path.endswith("/__init__.py") and path[:-3] + ".ts" in paths)
    require(len(twins) <= entry["module_budget"], f"{len(twins)} py/ts twin modules under {entry['root']}; budget is {entry['module_budget']}")
    return f"twins={len(twins)}/{entry['module_budget']}"


def check_inventory(registry: dict[str, Any], sources: list[SourceFile]) -> tuple[dict[str, Any], str]:
    inventory_path = REPO_ROOT / registry["inventory"]
    committed = inventory_path.read_text(encoding="utf-8")
    inventory = build_inventory(REPO_ROOT, sources=sources)
    require(inventory["schema_version"] == INVENTORY_SCHEMA_VERSION, "inventory schema drift")
    require(render_inventory(inventory) == committed, f"{registry['inventory']} is stale; run python3.11 scripts/generate_semantic_inventory.py and commit the result")
    semantic_multi_value_forks = check_scope_declarations(registry, inventory)
    ratchets = registry["inventory_ratchets"]
    summary = inventory["summary"]
    parts = []
    for key in RATCHET_KEYS:
        actual = semantic_multi_value_forks if key == "multi_value_forks_semantic" else summary[key]
        require(actual <= ratchets[key], f"inventory {key} grew to {actual}; budget is {ratchets[key]}")
        require(
            ratchets[key] == BUDGET_ANCHOR[key],
            f"inventory {key} budget is {ratchets[key]} but BUDGET_ANCHOR pins {BUDGET_ANCHOR[key]}; "
            "the registry and the anchor move together in one diff (see BUDGET_ANCHOR in this smoke)",
        )
        parts.append(f"{key}={actual}/{ratchets[key]}")
    return inventory, " ".join(parts)


def main() -> int:
    registry = load_registry()
    coverage = check_coverage_floor(registry)
    sources = load_sources(REPO_ROOT)
    inventory, ratchets = check_inventory(registry, sources)
    check_owned_vocabularies(registry, inventory)
    check_literal_vocabularies(registry, sources)
    unknown_producers = check_producers(registry, sources)
    check_relations(registry)
    check_projections(registry)
    check_schema_version_owners(registry, sources)
    budgets = check_retirement_budgets(registry, sources)
    twins = check_dual_runtime_twins(registry)
    print("semantic-vocabulary-drift-smoke: ok")
    print("  " + coverage)
    print("  " + ratchets)
    print("  " + " ".join(budgets))
    print("  " + twins)
    print(f"  unresolved_producer_sites={len(unknown_producers)} (not proven safe)")
    uncovered = [name for name, v in registry['vocabularies'].items() if v['tier'] == 'kernel' and 'producers' not in v]
    print(f"  kernel_producer_coverage_pending={','.join(uncovered)}")
    if '--report' in sys.argv[1:]:
        for site in unknown_producers:
            print(f"  unknown_producer: {site}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Drift as error:
        print(f"semantic-vocabulary-drift-smoke: FAIL\n  {error}", file=sys.stderr)
        raise SystemExit(1)
