# Frontier test evidence classification

This classification prevents source inspection from being promoted into
behavioral evidence.

## BEHAVIORAL_STATE_TRANSITION

- `catalytic_frontier_live_terminal_lifecycle_selftest.cpp` executes capture,
  cancellation, admission, closure, sleep, and shutdown transitions.
- `catalytic_frontier_twin_rail_runtime_selftest.cpp` executes structural
  replay rejection, metadata rollback, numerical decoherence, inverse faults,
  restoration, and repeated same-backing calibration reuse.
- `catalytic_frontier_two_evidence_twin_rail_selftest.cpp` executes staged
  cancellation/poison, structural field rejection, metadata rollback,
  numerical decoherence, inverse faults, restoration, and seed zeroing.
- `test_catalytic_frontier_linux_sidecar.py` executes the callback timeout.

The native tests count as behavioral evidence only when compiled and executed
through `catalytic_frontier_native_test_binding.py`, which records compiler,
assertion, sanitizer, source, binary, link-input, and output identities.

## EXACT_BOUNDED_ORACLE

- `catalytic_frontier_two_evidence_exact_oracle.py` proves the bounded
  normalized-probability calibration identities and inverse controls. It is
  not production-runtime, precision-scaling, or model-facing evidence.

## STATIC_BINDING_CHECK

- `test_catalytic_frontier_live_terminal_boundary.py` and the historical
  twin-rail Python suites inspect source shape, route schedules, and artifact
  bindings. They do not prove lifecycle, custody, restoration, cancellation,
  or carrier causality.
- `test_catalytic_runner.py` validates declarative schema, frozen schedules,
  contact prohibition, and absence of legacy controller imports. It does not
  execute inference.

## LEGACY_PROVENANCE_CHECK

Five historical controller tests that require consumed build artifacts are
explicitly skipped with this classification. Their raw historical evidence
remains append-only; a stale artifact binding is not a current behavioral
failure and is not counted as a current proof.
