# Legacy twin-rail controllers

The `neo-exp-0094` through `neo-exp-0101` Python wrappers are historical
evidence readers only. Their nested predecessor imports, `.parent` references,
and global monkey-patching are retired from the active path.

The active static path is `scripts/catalytic_runner.py` plus immutable JSON
specifications in `scripts/experiment_specs/`. It imports no historical
controller.

Historical files remain in place because consumed results and runtime manifests
bind their exact identities. They must not be imported to create a successor:

- `catalytic_frontier_linux_twin_rail_successor.py`
- `catalytic_frontier_linux_twin_rail_counter_reset_successor.py`
- `catalytic_frontier_linux_twin_rail_one_token_terminal_successor.py`
- `catalytic_frontier_linux_twin_rail_numerical_quotient_successor.py`
- `catalytic_frontier_linux_twin_rail_unrelated_reuse_successor.py`
- `catalytic_frontier_linux_twin_rail_cache_enabled_consumer_successor.py`
- `catalytic_frontier_linux_twin_rail_second_unrelated_successor.py`
- `catalytic_frontier_linux_twin_rail_second_unrelated_audit_repair_successor.py`

This retirement changes no historical result or artifact hash.
