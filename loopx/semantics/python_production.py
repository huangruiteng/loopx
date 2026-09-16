"""Bounded Python production evidence; never execute inspected source.

Known values are syntactic result possibilities, not proof of reachable traces.
Unresolved expressions retain their source locations. Owner definitions alone,
comparison operands, comments and quoted examples are not production evidence.
"""
from __future__ import annotations

import ast
from collections import Counter
from dataclasses import dataclass
from typing import Mapping, TypeVar

from .inventory import SourceFile


@dataclass(frozen=True)
class Production:
    site: str
    line: int
    form: str
    values: frozenset[str]
    unresolved: bool
    blocker: str | None = None
    """Why the unknown portion stayed unknown; ``None`` when fully resolved.

    ``argument_name_only`` a field-named keyword argument, which never proves an
    output role. ``unstable_local`` a parameter, reassignment or shadowed name.
    ``call_result`` the value comes back from a call. ``dynamic_key`` a computed
    or non-literal subscript. ``serialized_value`` a string where an enum object
    was required. ``annotation_only`` a bare annotation that declares the field
    without a value. ``attribute_read`` an attribute of an unresolved object.
    ``typescript_dynamic`` the TypeScript scanner could not resolve the write.
    ``other`` anything else; it keeps the site visible.
    """


def _module(path: str) -> str:
    name = path.removesuffix('.py').replace('/', '.')
    return name.removesuffix('.__init__')


def _import_module(path: str, node: ast.ImportFrom) -> str:
    if not node.level:
        return node.module or ''
    package = _module(path) if path.endswith('/__init__.py') else _module(path).rpartition('.')[0]
    parts = package.split('.')
    return '.'.join(parts[:len(parts) - node.level + 1] + ([node.module] if node.module else []))


_TREES: dict[tuple[str, int], ast.Module] = {}


def _parsed(source: SourceFile) -> ast.Module:
    key = (source.path, hash(source.text))
    tree = _TREES.get(key)
    if tree is None:
        tree = _TREES[key] = ast.parse(source.text, filename=source.path)
    return tree


def _tracked_module(module: str, modules: Mapping[str, SourceFile]) -> SourceFile | None:
    base = module.replace('.', '/')
    return modules.get(f'{base}.py') or modules.get(f'{base}/__init__.py')


def _reexported(source: SourceFile, symbol: str, imports: Mapping[tuple[str, str], _Binding]) -> _Binding | None:
    """One hop only: ``source`` imports ``symbol`` unrenamed from its owner and never rebinds it.

    ``import X as X`` counts as unrenamed. A renamed import, a second hop through
    another module, a local class or assignment of the same name, or a later
    ``import`` of that name leaves the symbol unbound, so the consumer stays unknown.
    """
    value = None
    for node in _parsed(source).body:
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if (alias.asname or alias.name) == symbol:
                    unrenamed = alias.asname in (None, alias.name)
                    value = imports.get((_import_module(source.path, node), symbol)) if unrenamed else None
        elif isinstance(node, ast.Import):
            if any((alias.asname or alias.name.split('.')[0]) == symbol for alias in node.names):
                value = None
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id == symbol for t in targets):
                value = None
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == symbol:
            value = None
    return value


def enum_members(source: SourceFile, symbol: str, *, strict: bool = False) -> dict[str, str]:
    """Extract literal members, with fail-closed generation as an explicit mode.

    Inventory/observation may inspect a bounded subset. Generation must account
    for every declaration without executing source or inferring enum aliases
    from iteration (which omits aliases present in ``__members__``).
    """
    tree = ast.parse(source.text, filename=source.path)
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == symbol]
    if len(classes) != 1:
        raise ValueError(f'{source.path}::{symbol}: expected one owner class')
    result: dict[str, str] = {}
    for node in classes[0].body:
        target = None
        value = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            value = node.value
        if strict:
            if isinstance(node, ast.Pass) or (isinstance(node, ast.Expr)
                    and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
                continue
            names = [n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)]
            name = target.id if isinstance(target, ast.Name) else ','.join(names) or getattr(node, 'name', symbol)
            prefix = f'{source.path}:{node.lineno}: member {name}'
            if (not isinstance(target, ast.Name) or target.id.startswith('__')
                    or (target.id.startswith('_') and target.id.endswith('_'))):
                raise ValueError(f'{prefix}: unsupported owner declaration')
            if target.id in result:
                raise ValueError(f'{prefix}: duplicate member declaration')
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                raise ValueError(f'{prefix}: expected a literal string; computed members and aliases are unsupported')
            if value.value in result.values():
                original = next(k for k, v in result.items() if v == value.value)
                raise ValueError(f'{prefix}: aliases member {original}; owner and registry differ (aliases unsupported)')
        if (isinstance(target, ast.Name) and isinstance(value, ast.Constant)
                and isinstance(value.value, str)):
            result[target.id] = value.value
    return result


def python_literal_uses(source: SourceFile, field: str) -> set[str]:
    """Literal writes and direct dispatch operands; not alias/data-flow proof."""
    tree = ast.parse(source.text, filename=source.path)

    def reads(node: ast.AST) -> bool:
        if isinstance(node, ast.Name):
            return node.id == field
        if isinstance(node, ast.Attribute):
            return node.attr == field
        if isinstance(node, ast.Subscript):
            return isinstance(node.slice, ast.Constant) and node.slice.value == field
        if isinstance(node, ast.BoolOp):
            # Preserve the common neutral fallback without attributing a
            # different field selected by and/or to this action slot.
            return (isinstance(node.op, ast.Or) and reads(node.values[0])
                    and all(isinstance(value, ast.Constant) and value.value in ('', None)
                            for value in node.values[1:]))
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == 'str' and len(node.args) == 1:
                return reads(node.args[0])
            return (isinstance(node.func, ast.Attribute) and node.func.attr == 'get'
                    and bool(node.args) and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == field)
        return False

    def literals(node: ast.AST) -> set[str]:
        if isinstance(node, ast.Constant):
            return {node.value} if isinstance(node.value, str) and node.value else set()
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            return set().union(*(literals(item) for item in node.elts))
        if isinstance(node, ast.MatchValue):
            return literals(node.value)
        if isinstance(node, ast.MatchOr):
            return set().union(*(literals(pattern) for pattern in node.patterns))
        return set()

    # Production collection already separates conditional results from their
    # conditions and does not inspect strings containing sample source text.
    rows = scan_python_production(source, field=field, enums={})
    result = set().union(*(row.values for row in rows))
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for left, operator, right in zip(
                [node.left, *node.comparators[:-1]], node.ops, node.comparators, strict=True,
            ):
                if isinstance(operator, (ast.Eq, ast.NotEq, ast.Is, ast.IsNot, ast.In, ast.NotIn)) and reads(left):
                    result.update(literals(right))
                if isinstance(operator, (ast.Eq, ast.NotEq, ast.Is, ast.IsNot)) and reads(right):
                    result.update(literals(left))
        elif isinstance(node, ast.Match) and reads(node.subject):
            for case in node.cases:
                result.update(literals(case.pattern))
    return result


_Binding = TypeVar('_Binding')


def _qualified_bindings(source: SourceFile, tree: ast.Module, owners: Mapping[str, _Binding],
                        modules: Mapping[str, SourceFile] | None = None) -> dict[str, _Binding]:
    bindings = {owner.split('::')[1]: value for owner, value in owners.items()
                if owner.split('::')[0] == source.path}
    imports = {(_module(owner.split('::')[0]), owner.split('::')[1]): value
               for owner, value in owners.items()}
    symbols = {symbol for _, symbol in imports}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            module = _import_module(source.path, node)
            for alias in node.names:
                name = alias.asname or alias.name
                value = imports.get((module, alias.name))
                if value is None and modules is not None and alias.name in symbols:
                    # One unrenamed re-export hop through a tracked module binds the
                    # same owner; only names that are owner symbols are followed.
                    target = _tracked_module(module, modules)
                    if target is not None and target.path != source.path:
                        value = _reexported(target, alias.name, imports)
                if value is not None:
                    bindings[name] = value
                else:
                    bindings.pop(name, None)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bindings.pop(alias.asname or alias.name.split('.')[0], None)
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    bindings.pop(target.id, None)
    return bindings


def scan_python_production(
    source: SourceFile,
    *,
    field: str | None,
    enums: Mapping[str, Mapping[str, str]],
    return_functions: frozenset[str] = frozenset(),
    return_paths: Mapping[str, tuple[str | int, ...]] | None = None,
    call_arguments: Mapping[str, Mapping[str, int | None]] | None = None,
    modules: Mapping[str, SourceFile] | None = None,
) -> list[Production]:
    """Observe writes and owner-member results with bounded local resolution.

    ``enums`` maps module::Class to literal member values from tracked owners.
    Only imported owner classes (including aliases) or the local owner qualify;
    ``modules`` additionally lets one unrenamed re-export hop through a tracked
    module bind the owner. Longer chains and renamed re-exports stay unknown.
    Local aliases and complete branch selections resolve only at output sites.
    General reassignment and parameter shadowing become unknown. Explicit call
    metadata names only reviewed builder arguments; arbitrary calls are consumers.
    Nested function returns belong to that function, not a registered enclosure.
    """
    tree = ast.parse(source.text, filename=source.path)
    bindings = _qualified_bindings(source, tree, enums, modules)
    call_arguments = call_arguments or {}
    calls = _qualified_bindings(source, tree, call_arguments, modules)
    return_paths = return_paths or {}

    result: list[Production] = []

    def matches(node: ast.AST) -> bool:
        if isinstance(node, ast.Name):
            return node.id == field
        if isinstance(node, ast.Attribute):
            return node.attr == field
        return (isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant)
                and node.slice.value == field)

    def scan_scope(body: list[ast.stmt], scope: str, parameters: set[str]) -> None:
        nodes: list[ast.AST] = []
        nested: list[ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef] = []

        def collect(node: ast.AST) -> None:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                nested.append(node)
                return
            if isinstance(node, ast.Lambda):
                return
            nodes.append(node)
            for child in ast.iter_child_nodes(node):
                collect(child)
        for statement in body:
            collect(statement)
        assigned = Counter(n.id for n in nodes if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store))
        local_owner_names = {owner.split('::')[1] for owner in enums if owner.split('::')[0] == source.path}
        nested_names = {n.name for n in nested}
        if scope == '<module>':
            nested_names -= local_owner_names | {owner.split('::')[1] for owner in call_arguments
                                                   if owner.split('::')[0] == source.path}
        imported = set()
        if scope != '<module>':
            for node in nodes:
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    imported.update(alias.asname or alias.name.split('.')[0] for alias in node.names)
        exception_targets = {n.name for n in nodes if isinstance(n, ast.ExceptHandler) and n.name}
        deleted = {n.id for n in nodes if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Del)}
        shadows = set(assigned) | parameters | nested_names | imported | exception_targets | deleted
        local_bindings = {k: v for k, v in bindings.items() if k not in shadows}
        local_calls = {k: v for k, v in calls.items() if k not in shadows}
        single_values = {}
        for node in nodes:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                target = node.targets[0].id
                if assigned[target] == 1 and target not in parameters:
                    single_values[target] = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                target = node.target.id
                if assigned[target] == 1 and target not in parameters and node.value is not None:
                    single_values[target] = node.value

        def conditional_values(node: ast.If) -> dict[str, tuple[ast.AST, int]]:
            # A complete if/elif/else defining a local in each arm is one finite
            # selection. Partial branches, loops and general reassignments stay
            # unknown; no assignment is itself an enum production site.
            def arm(statements: list[ast.stmt]) -> dict[str, tuple[ast.AST, int]]:
                if len(statements) == 1 and isinstance(statements[0], ast.If):
                    return conditional_values(statements[0])
                definitions = {}
                for statement in statements:
                    if (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                            and isinstance(statement.targets[0], ast.Name)):
                        name = statement.targets[0].id
                        definitions[name] = (statement.value, definitions.get(name, (None, 0))[1] + 1)
                return {name: item for name, item in definitions.items() if item[1] == 1}
            left, right = arm(node.body), arm(node.orelse)
            return {name: (ast.copy_location(ast.IfExp(test=node.test, body=left[name][0],
                        orelse=right[name][0]), node), left[name][1] + right[name][1])
                    for name in left.keys() & right.keys()}

        for node in nodes:
            if isinstance(node, ast.If):
                for name, (value, count) in conditional_values(node).items():
                    if assigned[name] == count and name not in parameters:
                        single_values[name] = value

        # Resolve only local containers that have not been mutated or escaped.
        # A subscript write through an alias invalidates every alias, rather
        # than turning a stale initializer into false scalar output evidence.
        containers = {name for name, value in single_values.items()
                      if isinstance(value, (ast.List, ast.Dict, ast.Set))}
        aliases = [(name, value.id) for name, value in single_values.items() if isinstance(value, ast.Name)]
        unsafe: set[str] = set()

        def root_name(node: ast.AST) -> str | None:
            while isinstance(node, (ast.Attribute, ast.Subscript)):
                node = node.value
            return node.id if isinstance(node, ast.Name) else None

        for node in nodes:
            if isinstance(node, (ast.Attribute, ast.Subscript)) and isinstance(node.ctx, (ast.Store, ast.Del)):
                if name := root_name(node):
                    unsafe.add(name)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and (name := root_name(node.func)):
                    unsafe.add(name)
                for argument in [*node.args, *(kw.value for kw in node.keywords)]:
                    if isinstance(argument, ast.Name):
                        unsafe.add(argument.id)
        for group in (containers, unsafe):
            changed = True
            while changed:
                before = len(group)
                for left, right in aliases:
                    if left in group or right in group:
                        group.update((left, right))
                changed = len(group) != before
        for name in containers & unsafe:
            single_values.pop(name, None)

        def bound(node: ast.AST | None, seen: frozenset[str]) -> tuple[ast.AST | None, frozenset[str]]:
            while isinstance(node, ast.Name) and node.id in single_values and node.id not in seen:
                definition = single_values[node.id]
                if (definition.lineno, definition.col_offset) >= (node.lineno, node.col_offset):
                    break
                seen = seen | {node.id}
                node = definition
            return node, seen

        def index_value(node: ast.AST) -> str | int | None:
            if isinstance(node, ast.Constant) and type(node.value) in (str, int):
                return node.value
            if (isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub)
                    and isinstance(node.operand, ast.Constant) and type(node.operand.value) is int):
                return -node.operand.value
            return None

        def lookup(container: ast.AST | None, key: str | int | None) -> tuple[list[ast.AST], bool]:
            if isinstance(container, (ast.Tuple, ast.List)):
                if type(key) is int:
                    return ([container.elts[key]], False) if -len(container.elts) <= key < len(container.elts) else ([], blocked('dynamic_key'))
                if key is not None:
                    return [], blocked('dynamic_key')
                return list(container.elts), blocked('dynamic_key')
            if isinstance(container, ast.Dict):
                keys = [index_value(k) if k is not None else None for k in container.keys]
                if key is not None and all(k is not None for k in keys):
                    # Python dict construction keeps the last duplicate key.
                    found = [v for k, v in zip(keys, container.values, strict=True) if k == key]
                    return ([found[-1]], False) if found else ([], blocked('dynamic_key'))
                return list(container.values), blocked('dynamic_key')
            return [], blocked('unstable_local' if isinstance(container, ast.Name) else 'other')

        blockers: list[str] = []

        def blocked(label: str) -> bool:
            blockers.append(label)
            return True

        def resolve(node: ast.AST | None, seen: frozenset[str] = frozenset(), *, enum_only: bool = False) -> tuple[set[str], bool]:
            node, seen = bound(node, seen)
            if isinstance(node, ast.Constant):
                if isinstance(node.value, str):
                    return ({node.value} if node.value and not enum_only else set()), False
                return set(), node.value is not None and blocked('other')
            if isinstance(node, ast.Subscript):
                if isinstance(node.slice, ast.Slice) or (isinstance(node.slice, ast.Constant)
                        and type(node.slice.value) not in (str, int)):
                    return set(), blocked('dynamic_key')
                container, visited = bound(node.value, seen)
                choices, unknown = lookup(container, index_value(node.slice))
                known: set[str] = set()
                for value in choices:
                    part, unresolved = resolve(value, visited, enum_only=enum_only)
                    known.update(part)
                    unknown |= unresolved
                return known, unknown
            if isinstance(node, (ast.IfExp, ast.BoolOp)):
                operands = [node.body, node.orelse] if isinstance(node, ast.IfExp) else node.values
                parts = [resolve(value, seen, enum_only=enum_only) for value in operands]
                return set().union(*(values for values, _ in parts)), any(unknown for _, unknown in parts)
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == 'str' and node.func.id not in shadows
                    and len(node.args) == 1 and not node.keywords):
                return resolve(node.args[0], seen, enum_only=enum_only)
            if isinstance(node, ast.Attribute):
                member = node.value if node.attr == 'value' else node
                if isinstance(member, ast.Attribute) and isinstance(member.value, ast.Name):
                    members = local_bindings.get(member.value.id)
                    if members is not None:
                        if member.attr not in members:
                            raise ValueError(f'{source.path}:{node.lineno}: unknown owner member {member.attr}')
                        return {members[member.attr]}, False
                if node.attr == 'value' and isinstance(node.value, ast.Name):
                    return enum_object_value(node.value, seen)
                return set(), blocked('attribute_read')
            if isinstance(node, ast.Call):
                return set(), blocked('call_result')
            if isinstance(node, ast.Name):
                return set(), blocked('unstable_local')
            if node is None:
                return set(), blocked('other')
            return set(), blocked('other')

        def enum_object_value(node: ast.AST, seen: frozenset[str]) -> tuple[set[str], bool]:
            node, seen = bound(node, seen)
            if isinstance(node, ast.IfExp):
                parts = [enum_object_value(value, seen) for value in (node.body, node.orelse)]
                return set().union(*(v for v, _ in parts)), any(u for _, u in parts)
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in local_bindings:
                return resolve(node, seen, enum_only=True)
            # A serialized string (including Action.RUN.value) is not an enum
            # object with another .value attribute.
            return set(), blocked('serialized_value')

        def returned(node: ast.AST | None, path: tuple[str | int, ...], seen: frozenset[str] = frozenset()) -> tuple[set[str], bool]:
            if not path:
                return resolve(node, seen)
            node, seen = bound(node, seen)
            choices, unknown = lookup(node, path[0])
            parts = [returned(value, path[1:], seen) for value in choices]
            return set().union(*(v for v, _ in parts)), unknown or any(u for _, u in parts)

        def record(node: ast.AST | None, form: str, location: ast.AST) -> None:
            blockers.clear()
            values, unknown = (returned(node, return_paths.get(scope, ())) if form == 'return' else resolve(node))
            blocker = blockers[0] if blockers else None
            if node is None and form == 'assignment':
                # A bare annotation declares the field; there is no value to resolve.
                blocker = 'annotation_only'
            if form == 'keyword_unproved':
                # Argument name alone does not prove an output role.
                unknown, blocker = True, 'argument_name_only'
            result.append(Production(f'{source.path}::{scope}', location.lineno, form,
                                     frozenset(values), unknown, blocker if unknown else None))

        for node in nodes:
            if isinstance(node, ast.Assign):
                if field and any(matches(t) for t in node.targets):
                    record(node.value, 'assignment', node)
            elif isinstance(node, ast.AnnAssign) and field and matches(node.target):
                record(node.value, 'assignment', node)
            elif isinstance(node, ast.Dict) and field:
                for key, value in zip(node.keys, node.values, strict=True):
                    if isinstance(key, ast.Constant) and key.value == field:
                        record(value, 'dict', node)
            elif isinstance(node, ast.Call):
                output_arguments = local_calls.get(node.func.id, {}) if isinstance(node.func, ast.Name) else {}
                for kw in node.keywords:
                    if kw.arg in output_arguments:
                        record(kw.value, 'call_argument', node)
                    elif field and kw.arg == field:
                        record(kw.value, 'keyword_unproved', node)
                for position in output_arguments.values():
                    if position is not None and position < len(node.args):
                        record(node.args[position], 'call_argument', node)
            elif isinstance(node, ast.Return) and node.value is not None:
                if scope in return_functions:
                    record(node.value, 'return', node)
                else:
                    values, unknown = resolve(node.value, enum_only=True)
                    if values:
                        result.append(Production(f'{source.path}::{scope}', node.lineno, 'enum_result', frozenset(values), unknown))
        for child in nested:
            name = child.name if scope == '<module>' else f'{scope}.{child.name}'
            params: set[str] = set()
            if not isinstance(child, ast.ClassDef):
                args = child.args
                params = {a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)}
                params.update(a.arg for a in (args.vararg, args.kwarg) if a)
            # A nested closure might shadow an owner in any enclosing scope.
            scan_scope(child.body, name, params | shadows)

    scan_scope(tree.body, '<module>', set())
    return sorted(set(result), key=lambda row: (row.site, row.line, row.form, sorted(row.values)))
