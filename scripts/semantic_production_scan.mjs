#!/usr/bin/env node
// Parse supplied tracked source text only; never load or execute product modules.
import ts from 'typescript';

let input = '';
for await (const chunk of process.stdin) input += chunk;
const request = JSON.parse(input);
const result = [];
for (const source of request.sources) {
  const tree = ts.createSourceFile(source.path, source.text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
  if (tree.parseDiagnostics.length) {
    const line = tree.getLineAndCharacterOfPosition(tree.parseDiagnostics[0].start ?? 0).line + 1;
    process.stdout.write(JSON.stringify({error: {path: source.path, line, code: "typescript_syntax"}}));
    process.exit(2);
  }
  const field = request.field;
  const returns = new Set((request.return_functions ?? []).filter(x => x.startsWith(`${source.path}::`)));
  const unwrap = node => {
    while (node && (ts.isParenthesizedExpression(node) || ts.isAsExpression(node) ||
      ts.isSatisfiesExpression(node) || ts.isNonNullExpression(node))) node = node.expression;
    return node;
  };
  // Say why a write stayed unknown using the same labels as the Python scanner,
  // so one residue taxonomy covers both runtimes instead of a single catch-all.
  const blockerFor = node => {
    if (!node) return 'other';
    if (ts.isPropertyAccessExpression(node) || ts.isElementAccessExpression(node)) return 'attribute_read';
    if (ts.isCallExpression(node) || ts.isNewExpression(node) || ts.isAwaitExpression(node)) return 'call_result';
    if (ts.isIdentifier(node)) return 'unstable_local';
    // `other`, not `dynamic_key`: the shared vocabulary defines `dynamic_key`
    // as a computed or non-literal subscript, and none of these is one. Python
    // answers `other` for the same shapes -- a dict literal or an f-string
    // where a scalar was required -- so the two runtimes agree on the label.
    if (ts.isObjectLiteralExpression(node) || ts.isArrayLiteralExpression(node) ||
      ts.isTemplateExpression(node)) return 'other';
    return 'typescript_dynamic';
  };
  // The scanner has no scope model, so it cannot tell the builtin `String`
  // from a parameter that shadows it, nor the `undefined` literal from a
  // local of that name. A caller-supplied `String` can return anything, so
  // trusting the builtin reading would report a produced value the code never
  // produces. Shadowing is therefore detected per file -- coarser than per
  // scope, which can only withhold a builtin reading, never invent one.
  const shadowedGlobals = new Set();
  {
    const noteName = name => {
      if (!name) return;
      if (ts.isIdentifier(name)) shadowedGlobals.add(name.text);
      else if (ts.isObjectBindingPattern(name) || ts.isArrayBindingPattern(name))
        for (const element of name.elements) if (ts.isBindingElement(element)) noteName(element.name);
    };
    const collect = node => {
      if (ts.isParameter(node) || ts.isVariableDeclaration(node) || ts.isBindingElement(node)) noteName(node.name);
      else if (ts.isFunctionDeclaration(node) || ts.isClassDeclaration(node)) noteName(node.name);
      else if (ts.isImportSpecifier(node) || ts.isImportClause(node) || ts.isNamespaceImport(node)) noteName(node.name);
      ts.forEachChild(node, collect);
    };
    collect(tree);
  }
  const merge = parts => ({
    values: [...new Set(parts.flatMap(part => part.values))].sort(),
    unresolved: parts.some(part => part.unresolved),
    blocker: parts.find(part => part.unresolved)?.blocker,
  });
  const values = expression => {
    const node = unwrap(expression);
    if (!node) return {values: [], unresolved: true, blocker: 'other'};
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return {values: node.text ? [node.text] : [], unresolved: false};
    if (node.kind === ts.SyntaxKind.NullKeyword) return {values: [], unresolved: false};
    // ``undefined`` carries no value and is not an unknown, matching the way
    // the Python scanner treats an explicit ``None``.
    if (ts.isIdentifier(node) && node.text === 'undefined' && !shadowedGlobals.has('undefined')) return {values: [], unresolved: false};
    if (ts.isConditionalExpression(node)) return merge([values(node.whenTrue), values(node.whenFalse)]);
    // ``a || b`` and ``a ?? b`` are a finite selection, exactly like the
    // Python scanner's BoolOp arms; ``String(x)`` is a transparent wrapper.
    if (ts.isBinaryExpression(node) && [ts.SyntaxKind.BarBarToken,
      ts.SyntaxKind.QuestionQuestionToken].includes(node.operatorToken.kind)) {
      return merge([values(node.left), values(node.right)]);
    }
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) &&
      node.expression.text === 'String' && node.arguments.length === 1 &&
      !shadowedGlobals.has('String')) return values(node.arguments[0]);
    return {values: [], unresolved: true, blocker: blockerFor(node)};
  };
  const staticName = expression => {
    const node = unwrap(expression);
    return node && (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) ? node.text : null;
  };
  const named = node => {
    if (!node) return null;
    if (ts.isComputedPropertyName(node)) return staticName(node.expression);
    return ts.isIdentifier(node) ? node.text : staticName(node);
  };
  const target = node => ts.isIdentifier(node) ? node.text === field
    : ts.isPropertyAccessExpression(node) ? node.name.text === field
      : ts.isElementAccessExpression(node) && staticName(node.argumentExpression) === field;
  const reads = expression => {
    const node = unwrap(expression);
    if (!node) return false;
    if (target(node)) return true;
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) &&
        node.expression.text === 'String' && node.arguments.length === 1 &&
        !shadowedGlobals.has('String')) return reads(node.arguments[0]);
    return ts.isBinaryExpression(node) &&
      [ts.SyntaxKind.BarBarToken, ts.SyntaxKind.QuestionQuestionToken].includes(node.operatorToken.kind) &&
      reads(node.left) && (staticName(node.right) === "" || unwrap(node.right).kind === ts.SyntaxKind.NullKeyword);
  };
  const literals = expression => {
    const node = unwrap(expression);
    if (!node) return [];
    if (ts.isArrayLiteralExpression(node)) return node.elements.flatMap(literals);
    if (ts.isNewExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'Set') {
      return (node.arguments ?? []).flatMap(literals);
    }
    return values(node).values;
  };
  function walk(node, scope) {
    if (ts.isFunctionDeclaration(node) || ts.isMethodDeclaration(node)) scope = scope === '<module>' ? named(node.name) : `${scope}.${named(node.name)}`;
    else if (ts.isArrowFunction(node) || ts.isFunctionExpression(node)) {
      const parent = node.parent;
      const name = ts.isVariableDeclaration(parent) || ts.isPropertyAssignment(parent) ? named(parent.name) : null;
      scope = name ? (scope === '<module>' ? name : `${scope}.${name}`) : '<anonymous>';
    }
    let expression, form;
    if (ts.isPropertyAssignment(node) && named(node.name) === field) { expression = node.initializer; form = 'object'; }
    else if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.EqualsToken && target(node.left)) { expression = node.right; form = 'assignment'; }
    else if (ts.isVariableDeclaration(node) && named(node.name) === field && node.initializer) { expression = node.initializer; form = 'assignment'; }
    else if (ts.isReturnStatement(node) && returns.has(`${source.path}::${scope}`)) { expression = node.expression; form = 'return'; }
    if (form) {
      result.push({site: `${source.path}::${scope}`, line: tree.getLineAndCharacterOfPosition(node.getStart(tree)).line + 1, form, ...values(expression)});
    }
    if (request.mode === 'literal_uses') {
      let observed = [];
      if (ts.isBinaryExpression(node) && [ts.SyntaxKind.EqualsEqualsToken,
        ts.SyntaxKind.EqualsEqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsToken,
        ts.SyntaxKind.ExclamationEqualsEqualsToken].includes(node.operatorToken.kind)) {
        if (reads(node.left)) observed.push(...literals(node.right));
        if (reads(node.right)) observed.push(...literals(node.left));
      } else if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression) &&
        ['includes', 'has'].includes(node.expression.name.text) && node.arguments.some(reads)) {
        observed.push(...literals(node.expression.expression));
      } else if (ts.isSwitchStatement(node) && reads(node.expression)) {
        for (const clause of node.caseBlock.clauses) if (ts.isCaseClause(clause)) observed.push(...literals(clause.expression));
      }
      if (observed.length) result.push({site: `${source.path}::${scope}`,
        line: tree.getLineAndCharacterOfPosition(node.getStart(tree)).line + 1,
        form: 'dispatch', values: observed, unresolved: false});
    }
    ts.forEachChild(node, child => walk(child, scope));
  }
  walk(tree, '<module>');
}
process.stdout.write(JSON.stringify(result));
