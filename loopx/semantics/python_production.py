"""Bounded Python production evidence; never execute inspected source.

Known values are syntactic result possibilities, not proof of reachable traces.
Unresolved expressions retain their source locations. Owner definitions alone,
comparison operands, comments and quoted examples are not production evidence.
"""
from __future__ import annotations

import ast
from collections import Counter
from dataclasses import dataclass
from typing import Mapping

from .inventory import SourceFile


@dataclass(frozen=True)
class Production:
    site: str
    line: int
    form: str
    values: frozenset[str]
    unresolved: bool


def _module(path: str) -> str:
    name = path.removesuffix('.py').replace('/', '.')
    return name.removesuffix('.__init__')


def _import_module(path: str, node: ast.ImportFrom) -> str:
    if not node.level:
        return node.module or ''
    package = _module(path) if path.endswith('/__init__.py') else _module(path).rpartition('.')[0]
    parts = package.split('.')
    return '.'.join(parts[:len(parts) - node.level + 1] + ([node.module] if node.module else []))


def enum_members(source: SourceFile, symbol: str) -> dict[str, str]:
    """Resolve only literal members from the declared owner class."""
    tree = ast.parse(source.text, filename=source.path)
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == symbol]
    if len(classes) != 1:
        raise ValueError(f'{source.path}::{symbol}: expected one owner class')
    result = {}
    for node in classes[0].body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                result[node.targets[0].id] = node.value.value
    return result


def scan_python_production(
    source: SourceFile,
    *,
    field: str | None,
    enums: Mapping[str, Mapping[str, str]],
    return_functions: frozenset[str] = frozenset(),
) -> list[Production]:
    """Observe writes and owner-member results with bounded local resolution.

    ``enums`` maps module::Class to literal member values from tracked owners.
    Only imported owner classes (including aliases) or the local owner qualify.
    A single local assignment can resolve a returned variable; reassignment and
    parameter shadowing become unknown. Nested function returns belong to that
    function and never to a registered enclosing function.
    """
    tree = ast.parse(source.text, filename=source.path)
    bindings: dict[str, Mapping[str, str]] = {}
    for owner, members in enums.items():
        path, symbol = owner.split('::')
        if path == source.path:
            bindings[symbol] = members
    owner_imports = {(_module(owner.split('::')[0]), owner.split('::')[1]): members
                     for owner, members in enums.items()}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname or alias.name
                members = owner_imports.get((_import_module(source.path, node), alias.name))
                if members is not None:
                    bindings[name] = members
                else:
                    bindings.pop(name, None)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bindings.pop(alias.asname or alias.name.split('.')[0], None)
    # Module assignments can shadow imported owners; never silently trust them.
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    bindings.pop(target.id, None)

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
            nested_names -= local_owner_names
        imported = set()
        if scope != '<module>':
            for node in nodes:
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    imported.update(alias.asname or alias.name.split('.')[0] for alias in node.names)
        exception_targets = {n.name for n in nodes if isinstance(n, ast.ExceptHandler) and n.name}
        deleted = {n.id for n in nodes if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Del)}
        shadows = set(assigned) | parameters | nested_names | imported | exception_targets | deleted
        local_bindings = {k: v for k, v in bindings.items() if k not in shadows}
        single_values = {}
        for node in nodes:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                target = node.targets[0].id
                if assigned[target] == 1 and target not in parameters:
                    single_values[target] = node.value

        def resolve(node: ast.AST | None, seen: frozenset[str] = frozenset()) -> tuple[set[str], bool]:
            if isinstance(node, ast.Constant):
                if isinstance(node.value, str):
                    return ({node.value} if node.value else set()), False
                return set(), node.value is not None
            if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Dict):
                known: set[str] = set()
                for value in node.value.values:
                    part, _ = resolve(value, seen)
                    known.update(part)
                # The key domain and lookup failure are not proved here.
                return known, True
            if isinstance(node, ast.IfExp):
                left, lu = resolve(node.body, seen)
                right, ru = resolve(node.orelse, seen)
                return left | right, lu or ru
            if isinstance(node, ast.BoolOp):
                known: set[str] = set()
                unknown = False
                for operand in node.values:
                    part, unresolved = resolve(operand, seen)
                    known.update(part)
                    unknown |= unresolved
                return known, unknown
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == 'str' and node.func.id not in shadows
                    and len(node.args) == 1 and not node.keywords):
                return resolve(node.args[0], seen)
            if isinstance(node, ast.Name) and node.id in single_values and node.id not in seen:
                definition = single_values[node.id]
                if (definition.lineno, definition.col_offset) < (node.lineno, node.col_offset):
                    return resolve(definition, seen | {node.id})
            if isinstance(node, ast.Attribute):
                member = node.value if node.attr == 'value' else node
                if isinstance(member, ast.Attribute) and isinstance(member.value, ast.Name):
                    members = local_bindings.get(member.value.id)
                    if members is not None:
                        if member.attr not in members:
                            raise ValueError(f'{source.path}:{node.lineno}: unknown owner member {member.attr}')
                        return {members[member.attr]}, False
            return set(), True

        def has_owner(node: ast.AST) -> bool:
            return any(isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                       and n.value.id in local_bindings for n in ast.walk(node))

        def enum_results(node: ast.AST | None) -> set[str]:
            # Inspect result positions only. Keys, conditions and comparison
            # operands describe selection; they are not produced enum values.
            if isinstance(node, ast.Attribute):
                return resolve(node)[0]
            if isinstance(node, ast.IfExp):
                return enum_results(node.body) | enum_results(node.orelse)
            if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
                return set().union(*(enum_results(part) for part in node.elts))
            if isinstance(node, ast.Dict):
                return set().union(*(enum_results(value) for value in node.values))
            if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Dict):
                return enum_results(node.value)
            return set()

        def record(node: ast.AST | None, form: str, location: ast.AST) -> None:
            values, unknown = resolve(node)
            if form == 'enum_result':
                values = enum_results(node)
            result.append(Production(f'{source.path}::{scope}', location.lineno, form, frozenset(values), unknown))

        for node in nodes:
            if isinstance(node, ast.Assign):
                if field and any(matches(t) for t in node.targets):
                    record(node.value, 'assignment', node)
                elif scope != '<module>' and has_owner(node.value):
                    record(node.value, 'enum_result', node)
            elif isinstance(node, ast.AnnAssign) and field and matches(node.target):
                record(node.value, 'assignment', node)
            elif isinstance(node, ast.Dict) and field:
                for key, value in zip(node.keys, node.values, strict=True):
                    if isinstance(key, ast.Constant) and key.value == field:
                        record(value, 'dict', node)
            elif isinstance(node, ast.Call):
                for kw in node.keywords:
                    if field and kw.arg == field:
                        record(kw.value, 'keyword', node)
                    elif has_owner(kw.value):
                        record(kw.value, 'enum_result', node)
                for arg in node.args:
                    if has_owner(arg) and not isinstance(arg, ast.Compare):
                        record(arg, 'enum_result', node)
            elif isinstance(node, ast.Return) and node.value is not None:
                if scope in return_functions:
                    record(node.value, 'return', node)
                elif has_owner(node.value) and not isinstance(node.value, (ast.Compare, ast.Dict)):
                    record(node.value, 'enum_result', node)
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
