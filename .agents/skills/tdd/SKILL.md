---
name: tdd
description: Implement software changes with strict test-driven development. Use when adding features, changing behavior, fixing bugs, or refactoring tested code, and when planning or reviewing a TDD implementation workflow.
---

# Test-driven development

Use one small Red-Green-Refactor cycle at a time. Do not write production behavior before a test requires it.

## Before the first cycle

1. Read the repository instructions and relevant code.
2. Identify the requested observable behavior and acceptance criteria. Ask the user when a material requirement is unclear.
3. Run the relevant existing tests to establish a green baseline. Report unrelated failures; do not hide them.
4. Make a short scenario list. This is a planning list, not a batch of executable tests.
5. Select the smallest valuable behavior from the list.

## Red

1. Add one focused test for the selected behavior.
2. Test through a public interface where practical. Assert outputs, state changes, errors, or durable side effects rather than private structure.
3. Run the narrowest useful test command.
4. Confirm that the new test fails for the expected reason because the behavior is missing.
5. If it passes immediately, improve the test or choose a missing behavior. If it fails because of syntax, setup, imports, or infrastructure, fix that problem and rerun until the failure proves the missing behavior.

Do not add several behaviors in one cycle. Do not write the full test suite before implementation.

## Green

1. Make the smallest clear production change that satisfies the failing test.
2. Do not add speculative features or abstractions.
3. Run the focused test, then all relevant existing tests.
4. Confirm that the new and existing tests pass.

Do not delete assertions, weaken expectations, copy observed output into expected output, or change requirements only to obtain a passing test. Change a test only when the requirement changed, the test is wrong, or its setup must change while preserving the same behavior assertion.

## Refactor

1. Refactor only while tests are green.
2. Improve names, duplication, boundaries, and design without changing observable behavior.
3. Keep transformations small and rerun relevant tests after each material change.
4. End the cycle green before selecting the next scenario.

Do not combine an intended behavior change with a refactor step.

## Test design

- Keep tests deterministic, isolated, readable, and fast enough for their feedback role.
- Control time, randomness, environment, and generated identifiers when they affect results.
- Give each test its own state. Do not depend on test order or state left by another test.
- Prefer representative values and clear assertions. Cover edge cases when each one expresses distinct behavior.
- Avoid tests coupled to private methods, incidental data layout, or exact call sequences.
- A pure internal refactor should not require behavior tests to change.

Choose scope by risk:

- Use unit tests for domain rules, calculations, transformations, and edge cases.
- Use integration tests for databases, files, serialization, framework wiring, protocols, and component contracts.
- Use a small number of end-to-end tests for critical user workflows.

Prefer a real collaborator when it is local, fast, deterministic, and easy to configure. Use a fake or stub for a dependency that is remote, slow, nondeterministic, destructive, unavailable, or needed to produce a rare failure. Add integration or contract coverage for substituted boundaries. Use interaction mocks only when the interaction itself is required behavior.

## Bugs

1. Add the smallest test that reproduces the reported bug.
2. Run it and confirm the expected failure.
3. Apply the smallest fix.
4. Confirm the regression test and relevant suite pass.
5. Refactor only after green. Keep the regression test.

## Existing untested code

1. Characterize current observable behavior around the change area.
2. Add the smallest safe seam needed to control a difficult dependency.
3. Preserve unrelated current behavior.
4. Implement the requested change with normal Red-Green-Refactor cycles.

## Completion

Before reporting completion:

1. Run the focused tests and the relevant broader suite.
2. Check that each requested acceptance criterion has test coverage at the correct level.
3. State the test commands run and their final results.
4. Summarize the behavior implemented and any untested risk or blocked test.

Never claim TDD if the failing test was not observed before its production change. If constraints prevented a true test-first cycle, state that clearly.

See `references/sources.md` for the principles and primary references behind this workflow.
