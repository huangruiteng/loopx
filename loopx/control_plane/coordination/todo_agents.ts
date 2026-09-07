import {AuthorityStoreProtocolError} from "./authority_store_codec.ts";

// Python str.split() and isspace() recognize exactly 29 Unicode whitespace
// code points: ASCII \t\n\v\f\r and space, ASCII information separators
// U+001C..U+001F, the C1 control NEL (U+0085), and Unicode whitespace blocks
// (NBSP U+00A0, Ogham space mark U+1680, en/em/thin spaces U+2000..U+200A,
// line/paragraph separators U+2028/U+2029, mathematical/ideographic spaces
// U+202F/U+205F/U+3000). Notably, ECMAScript \s omits U+001C..U+001F and
// U+0085 while including BOM (U+FEFF), which Python rejects as whitespace.
// Explicitly match Python's exact 29-code-point whitespace set.
const PYTHON_WHITESPACE_CLASS =
  "[\\t\\n\\v\\f\\r \\u001c-\\u001f\\u0085\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000]";
const PYTHON_LEADING_TRAILING_WHITESPACE = new RegExp(
  `^${PYTHON_WHITESPACE_CLASS}+|${PYTHON_WHITESPACE_CLASS}+$`,
  "gu",
);
const PYTHON_WHITESPACE_RUN = new RegExp(`${PYTHON_WHITESPACE_CLASS}+`, "gu");

/** Strip exactly the characters removed by Python str.strip(). */
export function stripPythonWhitespace(value: string): string {
  return value.replace(PYTHON_LEADING_TRAILING_WHITESPACE, "");
}

/** Match Python's bool(str(value).strip()) presence contract. */
export function hasPythonNonWhitespaceText(value: string): boolean {
  return stripPythonWhitespace(value).length > 0;
}

export function normalizeTodoAgent(value: unknown, label: string): string {
  if (typeof value !== "string") {
    throw new AuthorityStoreProtocolError(`${label} must be a public-safe agent id`);
  }
  // Trim and collapse every Python-equivalent whitespace run to one "-" so ids
  // typed with any Python whitespace (including U+0085 NEL, U+001C..U+001F,
  // tabs, and NBSP) fold exactly like the Python kernel's compact_todo_text path
  // (loopx/control_plane/todos/contract.py normalize_todo_claimed_by).
  const stripped = stripPythonWhitespace(value);
  const candidate = stripped.toLowerCase().replace(PYTHON_WHITESPACE_RUN, "-");
  if (!/^[a-z][a-z0-9_.:@-]{0,79}$/u.test(candidate)) {
    throw new AuthorityStoreProtocolError(`${label} must be a public-safe agent id`);
  }
  return candidate;
}

export function normalizeRegisteredTodoAgents(value: readonly string[]): string[] {
  if (!Array.isArray(value)) {
    throw new AuthorityStoreProtocolError("registered_agents must be an array");
  }
  const normalized = value.map((agent, index) =>
    normalizeTodoAgent(agent, `registered_agents[${index}]`)
  );
  if (new Set(normalized).size !== normalized.length) {
    throw new AuthorityStoreProtocolError(
      "registered_agents must contain unique public-safe agent ids",
    );
  }
  return normalized;
}
