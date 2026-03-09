# Code Review Rules

This document defines mandatory review standards using **MUST**, **SHOULD**, and **MUST NOT**.

## MUST

- **Keep code readable and concise.** Prefer simple, clear implementations (KISS).
- **Remove redundancy.** Eliminate dead code, unused variables/imports, and duplicated logic.
- **Preserve testability.** Favor decoupled, unit-testable functions/classes and dependency injection where needed.
- **Use explicit typing.** New and modified code must include type hints consistent with PEP 484.
- **Pass static analysis.** Changes must pass:
  - `mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs`
  - `flake8`
- **Follow style/doc conventions.** Adhere to PEP 8 and PEP 257.

## SHOULD

- **Prefer Pythonic solutions.** Use idiomatic Python and standard-library tools before custom implementations.
- **Apply YAGNI pragmatically.** Introduce abstractions only when there is a present, concrete need.
- **Balance architecture and simplicity.** Use SOLID/Clean Code principles when they improve maintainability without overengineering.
- **Optimize only with evidence.** Use profiling or clear performance data before proposing non-trivial optimizations.

## MUST NOT

- **Must not introduce global mutable state** unless there is a clear, documented, unavoidable reason.
- **Must not suggest non-Pythonic patterns** when a native, clearer alternative exists.
- **Must not overengineer** with speculative abstractions for hypothetical future requirements.
- **Must not reinvent standard-library behavior** already provided by modules such as `itertools`, `collections`, or `pathlib`.
- **Must not use bare `except:`** blocks.

## Exception Handling Policy

- Catching `Exception` is **disallowed inside core domain logic**.
- Catching `Exception` is **allowed at application boundaries** (e.g., CLI entrypoints, render/game loop boundaries) only if all of the following are true:
  - the error is logged or printed clearly,
  - control flow is explicit (exit/re-raise/fallback is intentional),
  - no errors are silently swallowed.

## Review Checklist (PR Gate)

- [ ] Readability improved or preserved.
- [ ] No dead code / unused variables / duplicate logic introduced.
- [ ] Type hints added/updated where needed.
- [ ] `mypy` passes with configured flags.
- [ ] `flake8` passes.
- [ ] Tests updated for behavior changes.