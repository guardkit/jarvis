# DDR-007: `calculate` uses `asteval` for safe expression evaluation

- **Status:** Accepted
- **Date:** 2026-04-23
- **Session:** `/system-design FEAT-JARVIS-002`
- **Related components:** External Tool Context; `jarvis.tools.general.calculate`

## Context

The Phase 2 scope document specifies *"wraps `mathjs`-style safe evaluation (no `eval`)"* and leaves the library choice open. Python has several options, each with distinct safety and surface-area trade-offs.

The requirement: the reasoning model passes a user-visible expression string (e.g. `"15% of 847"`, `"sqrt(2) * 10"`, `"2 ** 32"`), and the tool returns a numeric result or a structured error. No variables, no functions outside a small allow-list, no file access, no network access, no unbounded loops.

## Decision

**Use `asteval` (by Matt Newville, MIT-licensed).** It evaluates Python expressions by parsing to AST and walking it with a per-instance symbol table, forbidding function definitions, imports, and unsafe attribute access by default. The allow-list of mathematical builtins (`sqrt`, `log`, `exp`, `sin`, `cos`, `tan`, `abs`, `min`, `max`, `round`, plus operators `+ - * / ** %`) is injected into the interpreter at construction.

Phase 2 `calculate` flow:

1. Pre-filter expression: reject if it contains `import`, `lambda`, `class`, `def`, `=` (assignment), `__` (dunder access), or `\n`. Returns `ERROR: unsafe_expression — disallowed token: <token>`.
2. Normalise percent syntax: `"15% of 847"` → `"0.15 * 847"` via a small regex. This is a user-affordance so the docstring's example works.
3. Invoke `asteval.Interpreter(symtable=MATH_BUILTINS, max_time=1.0)` on the normalised expression.
4. If `interp.error` is non-empty, return `ERROR: parse_error — <first error message>`.
5. Catch `ZeroDivisionError`, `OverflowError`, `ValueError` at the tool boundary; convert to `ERROR: division_by_zero`, `ERROR: overflow`, `ERROR: parse_error`.
6. Return the result as a string (`repr(result)` for ints, `f"{result:g}"` for floats to avoid noisy trailing zeros).

## Alternatives considered

1. **Python `ast.literal_eval`.** Rejected — only evaluates literal structures (numbers, strings, tuples, lists, dicts, booleans, None). Doesn't support arithmetic operators or math functions.
2. **`simpleeval`.** Considered. Smaller API surface than `asteval`, comparable safety. Picked `asteval` because it's already used by NumPy's parameter-file loader and specialist-agent, so the fleet has prior exposure. Rollback is trivial if needed — the `Interpreter()` API is almost identical.
3. **Sympy.** Rejected — too heavy (50 MB+ install) for a calculator tool; would balloon Jarvis's image size. Also gives symbolic results by default, which would need re-coercion.
4. **Write our own AST walker.** Rejected — reinventing a well-maintained library is a security-surface liability.
5. **Use the LLM itself to compute.** Explicitly rejected — the tool exists precisely *because* the LLM is unreliable at arithmetic. This is the tool's raison d'être per ADR-ARCH-016-equivalent ("prefer tools over mental work").

## Consequences

- **+** Small, well-maintained dependency (`asteval >= 0.9.33`).
- **+** The tool is genuinely safe against expression injection — no code execution, no symbol table bleed.
- **+** `asteval.Interpreter(max_time=1.0)` terminates runaway expressions (e.g. `10**100**100`) without killing the host process.
- **+** Tests are straightforward: pass expressions, assert on returned strings or error prefixes.
- **−** `asteval`'s error messages are Pythonic and sometimes verbose. Mitigation: the tool truncates to a single line in the `ERROR: parse_error — <detail>` return.
- **−** Adds one dependency. Mitigation: `asteval` is ~40 KB of pure Python with only `numpy` as an optional dependency which Jarvis already has transitively.
