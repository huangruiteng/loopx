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
    while (node && (ts.isParenthesizedExpression(node) || ts.isAsExpression(node) || ts.isSatisfiesExpression(node))) node = node.expression;
    return node;
  };
  const values = expression => {
    const node = unwrap(expression);
    if (!node) return {values: [], unresolved: true};
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return {values: node.text ? [node.text] : [], unresolved: false};
    if (node.kind === ts.SyntaxKind.NullKeyword) return {values: [], unresolved: false};
    if (ts.isConditionalExpression(node)) {
      const left = values(node.whenTrue), right = values(node.whenFalse);
      return {values: [...new Set([...left.values, ...right.values])].sort(), unresolved: left.unresolved || right.unresolved};
    }
    return {values: [], unresolved: true};
  };
  const named = node => node && (ts.isIdentifier(node) || ts.isStringLiteral(node)) ? node.text : null;
  const target = node => ts.isIdentifier(node) ? node.text === field
    : ts.isPropertyAccessExpression(node) ? node.name.text === field
      : ts.isElementAccessExpression(node) && ts.isStringLiteral(node.argumentExpression) && node.argumentExpression.text === field;
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
    ts.forEachChild(node, child => walk(child, scope));
  }
  walk(tree, '<module>');
}
process.stdout.write(JSON.stringify(result));
