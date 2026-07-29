from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import catalytic_frontier_linux_live_terminal_successor as candidate


class LinuxLiveTerminalSuccessorTests(unittest.TestCase):
    def tearDown(self) -> None:
        candidate.restore_inherited_geometry()

    def test_exact_linux_geometry_and_device_byte_law(self):
        self.assertEqual(
            (
                candidate.EXPECTED_RETAINED_TOKENS,
                candidate.EXPECTED_BASE_TOKENS,
                candidate.EXPECTED_BRANCH_TOKENS,
                candidate.EXPECTED_CHILD_TOKENS,
                candidate.EXPECTED_SUCCESSOR_TOKENS,
            ),
            (607, 684, 685, 690, 777),
        )
        self.assertEqual(candidate.EXPECTED_REBASE_FRESH_TOKENS, 6)
        self.assertEqual(candidate.EXPECTED_SUCCESSOR_FRESH_TOKENS, 87)
        self.assertEqual(candidate.EXPECTED_AVOIDED_PER_EDGE, 684)
        self.assertEqual(candidate.EXPECTED_COUNTED_AVOIDED_TOKENS, 4_104)
        self.assertEqual(candidate.EXPECTED_BASE_DEVICE_BYTES, 79_872_000)
        self.assertEqual(candidate.EXPECTED_CHILD_DEVICE_BYTES, 79_994_880)
        self.assertEqual(
            candidate.EXPECTED_SUCCESSOR_TERMINAL_DEVICE_BYTES,
            81_776_640,
        )

    def test_geometry_configuration_rebinds_without_editing_predecessor(self):
        values = candidate.configure_linux_geometry()
        self.assertEqual(
            candidate.predecessor.EXPERIMENT_ID,
            candidate.EXPERIMENT_ID,
        )
        self.assertEqual(
            candidate.predecessor.EXPECTED_REQUEST_SHA256,
            candidate.EXPECTED_REQUEST_SHA256,
        )
        self.assertIs(
            candidate.predecessor.derive_successor,
            candidate.derive_successor,
        )
        self.assertIs(
            candidate.predecessor.erase_child,
            candidate.dynamic_erase_child,
        )
        self.assertEqual(
            (
                candidate.predecessor.rebase.EXPECTED_COMPLETE_BRANCH_TOKENS,
                candidate.predecessor.rebase.EXPECTED_VISIBLE_OUTPUT_TOKENS,
                candidate.predecessor.rebase.EXPECTED_CHILD_TOKENS,
            ),
            (685, 5, 690),
        )
        self.assertEqual(values["EXPECTED_SUCCESSOR_TOKENS"], 777)

    def test_compact_child_accepts_all_linux_c_d_b_output_states(self):
        candidate.configure_linux_geometry()
        branch = list(range(candidate.EXPECTED_BRANCH_TOKENS))
        for ordinal, answer in enumerate(("C", "D", "B"), start=1):
            visible = [ordinal * 10 + index for index in range(5)]
            state = {
                "answer": answer,
                "visible_token_ids": visible,
                "generated_token_ids": [*visible, 248046],
                "terminal_eog_id": 248046,
            }
            child = candidate.predecessor.rebase.compact_child_tokens(
                branch,
                state,
            )
            self.assertEqual(len(child), candidate.EXPECTED_CHILD_TOKENS)
            self.assertEqual(child[: len(branch)], branch)
            self.assertEqual(child[-len(visible) :], visible)

    def test_payload_and_output_identities_are_prospectively_pinned(self):
        self.assertRegex(
            candidate.EXPECTED_SEED_PAYLOAD_SHA256,
            r"^[0-9A-F]{64}$",
        )
        self.assertEqual(
            set(candidate.EXPECTED_SUCCESSOR_PAYLOAD_SHA256),
            {False, True},
        )
        for value in (
            *candidate.EXPECTED_SUCCESSOR_PAYLOAD_SHA256[True].values(),
            *candidate.EXPECTED_SUCCESSOR_PAYLOAD_SHA256[False].values(),
            *candidate.EXPECTED_GENERATED_SHA256.values(),
            *candidate.EXPECTED_CHILD_SHA256.values(),
            *candidate.EXPECTED_REQUEST_SHA256.values(),
        ):
            self.assertRegex(value, r"^[0-9A-F]{64}$")

    def test_contract_binds_all_required_public_fields_before_output(self):
        candidate.configure_linux_geometry()
        contract = candidate.live.public_contract(
            trial_label="nonce-trial-1",
            edge=1,
            input_boundary_id=candidate.EXPECTED_REQUEST_SHA256["C"],
        )
        self.assertEqual(
            set(contract),
            {
                "boundary_id",
                "carrier_id",
                "outer_lease",
                "generation",
                "port_owner",
                "port_type",
                "module_id",
                "module_variant",
                "module_ordinal",
                "input_boundary_id",
                "projection_policy",
                "restoration_policy",
            },
        )
        self.assertEqual(contract["generation"], contract["module_ordinal"])
        self.assertEqual(
            contract["projection_policy"],
            "FINAL_TOKEN_STREAM_ONLY",
        )
        self.assertEqual(contract["restoration_policy"], "DECLARED_CLOSURE")
        self.assertNotIn("answer", contract)
        self.assertNotIn("output", contract)

    def test_every_tuple_field_has_an_independent_mutation(self):
        contract = {
            "boundary_id": "handle",
            "carrier_id": "carrier",
            "outer_lease": 1,
            "generation": 1,
            "port_owner": "owner",
            "port_type": "type",
            "module_id": "module",
            "module_variant": 0,
            "module_ordinal": 1,
            "input_boundary_id": "boundary",
            "projection_policy": "projection",
            "restoration_policy": "closure",
        }
        self.assertEqual(len(candidate.TUPLE_MUTATION_FIELDS), 12)
        for field in candidate.TUPLE_MUTATION_FIELDS:
            mutated = candidate.mutate_contract(contract, field)
            changed = {
                key for key in contract if contract[key] != mutated[key]
            }
            self.assertEqual(changed, {field})

    def test_every_tuple_field_dynamically_proves_poison_by_replay(self):
        source = Path(candidate.__file__).read_text(encoding="utf-8")
        controls = source[
            source.index("def run_tuple_controls(") :
            source.index("def generated_state(")
        ]
        self.assertIn(
            'label=f"poisoned-boundary-replay-{field}"',
            controls,
        )
        self.assertNotIn(
            "if field == TUPLE_MUTATION_FIELDS[0]",
            controls,
        )

    def test_matched_routes_orders_and_bounded_request_count_are_frozen(self):
        self.assertEqual(
            candidate.ROUTES,
            ("live-terminal", "root-only", "materialized"),
        )
        self.assertEqual(
            candidate.TRIAL_ROUTE_ORDERS,
            (
                ("live-terminal", "root-only", "materialized"),
                ("root-only", "materialized", "live-terminal"),
                ("materialized", "live-terminal", "root-only"),
            ),
        )
        self.assertEqual(candidate.EXPECTED_MODEL_CALLBACKS, 74)
        self.assertEqual(candidate.EXPECTED_DIRECT_PROTOCOL_ACTIONS, 27)

    def test_runtime_source_commit_requires_real_lowercase_ancestor(self):
        for malformed in (
            "",
            "a" * 39,
            "A" * 40,
            "g" * 40,
            "../" + "a" * 37,
        ):
            with self.assertRaisesRegex(
                candidate.ExperimentError,
                "lowercase full-length",
            ):
                candidate.validate_runtime_source_commit(
                    malformed,
                    require_current=False,
                )
        with mock.patch.object(
            candidate.subprocess,
            "run",
            side_effect=[
                mock.Mock(returncode=0),
                mock.Mock(returncode=1),
            ],
        ):
            with self.assertRaisesRegex(
                candidate.ExperimentError,
                "not an ancestor",
            ):
                candidate.validate_runtime_source_commit(
                    "a" * 40,
                    require_current=False,
                )

    def test_live_log_surface_requires_exact_boolean_contract(self):
        candidate.require_exact_live_log_surface(
            dict(candidate.EXPECTED_LIVE_LOG_SURFACE)
        )
        for malformed in (
            {},
            {"capture_logit_fingerprint_absent": "yes"},
            {
                **candidate.EXPECTED_LIVE_LOG_SURFACE,
                "extra": True,
            },
            {
                **candidate.EXPECTED_LIVE_LOG_SURFACE,
                "raw_logits_absent": False,
            },
        ):
            with self.assertRaisesRegex(
                candidate.ExperimentError,
                "log-surface proof changed",
            ):
                candidate.require_exact_live_log_surface(malformed)

    def test_cuda_object_manifest_binds_exact_paths_and_hashes(self):
        expected = [
            {
                "relative_path": (
                    "ggml/src/ggml-cuda/CMakeFiles/ggml-cuda.dir/"
                    f"unit-{ordinal:03d}.cu.o"
                ),
                "bytes": ordinal + 1,
                "sha256": f"{ordinal:064X}",
                "source_relative_path": (
                    "ggml/src/ggml-cuda/"
                    f"unit-{ordinal:03d}.cu"
                ),
                "source_bytes": ordinal + 1,
                "source_sha256": f"{ordinal:064X}",
                "source_git_blob_oid": f"{ordinal:040x}",
                "source_git_bytes": ordinal + 1,
                "source_git_sha256": f"{ordinal:064X}",
                "compile_command_sha256": f"{ordinal:064X}",
            }
            for ordinal in range(139)
        ]
        candidate.validate_cuda_object_records(expected, list(expected))
        changed = [dict(item) for item in expected]
        changed[-1]["sha256"] = "F" * 64
        with self.assertRaisesRegex(
            candidate.runtime.ExperimentError,
            "CUDA object identity closure",
        ):
            candidate.validate_cuda_object_records(expected, changed)
        changed_source = [dict(item) for item in expected]
        changed_source[-1]["source_sha256"] = "E" * 64
        with self.assertRaisesRegex(
            candidate.runtime.ExperimentError,
            "CUDA object identity closure",
        ):
            candidate.validate_cuda_object_records(
                expected,
                changed_source,
            )
        with self.assertRaisesRegex(
            candidate.ExperimentError,
            "exactly 139 identities",
        ):
            candidate.validate_cuda_object_records(expected, expected[:-1])

    def test_source_artifact_binds_worktree_and_git_filtered_blob(self):
        name = "server_entrypoint_source"
        path = candidate.RUNTIME_ARTIFACT_PATHS[name].resolve(strict=True)
        relative_path = path.relative_to(candidate.ROOT).as_posix()
        git_blob_oid = candidate.subprocess.check_output(
            [
                "git",
                "hash-object",
                f"--path={relative_path}",
                relative_path,
            ],
            cwd=candidate.ROOT,
            text=True,
        ).strip()
        git_blob = candidate.subprocess.check_output(
            ["git", "cat-file", "blob", git_blob_oid],
            cwd=candidate.ROOT,
        )
        artifact = {
            "relative_path": relative_path,
            **candidate.runtime.file_identity(path),
            "git_blob_oid": git_blob_oid,
            "git_bytes": len(git_blob),
            "git_sha256": candidate.hashlib.sha256(
                git_blob
            ).hexdigest().upper(),
        }
        with mock.patch.object(
            candidate,
            "SOURCE_ARTIFACT_NAMES",
            {name},
        ):
            candidate.validate_source_artifacts_at_commit(
                candidate.current_head(),
                {name: artifact},
            )
            changed = dict(artifact)
            changed["git_sha256"] = "F" * 64
            with self.assertRaisesRegex(
                candidate.ExperimentError,
                "does not match source commit",
            ):
                candidate.validate_source_artifacts_at_commit(
                    candidate.current_head(),
                    {name: changed},
                )

    def test_shutdown_custody_is_required_before_projection(self):
        source = Path(candidate.__file__).read_text(encoding="utf-8")
        main = source[source.rindex("def main() -> int:") :]
        self.assertIn(
            "shutdown_custody = audit_shutdown_live_terminal_custody(",
            main,
        )
        closure = main[
            main.index("closure = (") :
            main.index("if caught is None and not closure:")
        ]
        self.assertIn('shutdown_custody.get("passed") is True', closure)
        self.assertLess(
            main.index("cleanup = raw_sidecar.stop()"),
            main.index(
                "shutdown_custody = "
                "audit_shutdown_live_terminal_custody("
            ),
        )
        self.assertLess(
            main.index(
                "shutdown_custody = "
                "audit_shutdown_live_terminal_custody("
            ),
            main.index("terminal.write_exclusive_json(output, result)"),
        )

    def test_shutdown_custody_requires_exact_server_summary(self):
        sidecar = mock.Mock()
        sidecar.run_root = Path("/nonexistent/neo-exp-0091-run")
        with (
            mock.patch.object(Path, "is_file", return_value=True),
            mock.patch.object(Path, "is_symlink", return_value=False),
            mock.patch.object(
                Path,
                "read_text",
                return_value=(
                    "neo3000 one-use live terminal shutdown custody "
                    "poisoned=1 unresolved=0\n"
                ),
            ),
            mock.patch.object(
                candidate.harness.live_runtime,
                "sha256_file",
                return_value="A" * 64,
            ),
        ):
            receipt = candidate.audit_shutdown_live_terminal_custody(
                sidecar,
                {"pid": 123},
            )
        self.assertTrue(receipt["passed"])
        self.assertEqual(receipt["poisoned_boundaries"], 1)
        self.assertEqual(receipt["unresolved_boundaries"], 0)

        with (
            mock.patch.object(Path, "is_file", return_value=True),
            mock.patch.object(Path, "is_symlink", return_value=False),
            mock.patch.object(Path, "read_text", return_value=""),
        ):
            with self.assertRaisesRegex(
                candidate.ExperimentError,
                "exactly one live-boundary custody summary",
            ):
                candidate.audit_shutdown_live_terminal_custody(
                    sidecar,
                    {"pid": 123},
                )

    def test_first_transport_is_durably_consumed_before_callback(self):
        events: list[str] = []
        marker = Path("/nonexistent/neo-exp-0091-consumed.json")
        raw = mock.Mock()
        raw.run_root = Path("/nonexistent/neo-exp-0091-run")
        progress = {"scientific_contact": False, "transport_attempts": []}

        def guarded(label, callback, *, timeout, **kwargs):
            events.append(f"guarded:{label}")
            return callback()

        def write(path, payload):
            events.append(f"write:{Path(path).name}")
            return {"path": str(path), "sha256": "A" * 64}

        raw.guarded.side_effect = guarded
        proxy = candidate.ContactJournalSidecar(
            raw,
            progress,
            marker,
            "a" * 40,
        )

        def callback():
            self.assertEqual(len(events), 3)
            self.assertIn("consumption_marker", progress)
            self.assertTrue(progress["scientific_contact"])
            events.append("callback")
            return "ok"

        with mock.patch.object(
            candidate.terminal,
            "write_exclusive_json",
            side_effect=write,
        ):
            result = proxy.guarded(
                f"frontier:{candidate.EXPERIMENT_ID}:task-a",
                callback,
                timeout=1,
            )
        self.assertEqual(result, "ok")
        self.assertEqual(events[-1], "callback")

    def test_failure_projection_waits_for_process_port_and_lock_closure(self):
        source = Path(candidate.__file__).read_text(encoding="utf-8")
        main = source[source.rindex("def main() -> int:") :]
        self.assertLess(
            main.index("cleanup = raw_sidecar.stop()"),
            main.index("terminal.write_exclusive_json(output, result)"),
        )
        self.assertLess(
            main.index("lock_release = release_lock(lock_path)"),
            main.index("terminal.write_exclusive_json(output, result)"),
        )
        custody = main[
            main.index("custody_failure = {") :
            main.index("failure = full_failure if closure else custody_failure")
        ]
        self.assertNotIn("result_before_cleanup", custody)
        self.assertIn('"outcome_projection_withheld": True', custody)
        self.assertIn(
            'run_root / "precontact-failure.json"',
            main,
        )
        self.assertIn(
            "canonical_identity_consumed",
            main,
        )
        self.assertIn(
            "if caught is None and not closure:",
            main,
        )

    def test_runtime_revalidation_and_canonical_paths_precede_launch(self):
        source = Path(candidate.__file__).read_text(encoding="utf-8")
        main = source[source.rindex("def main() -> int:") :]
        self.assertLess(
            main.index("prelaunch_static = static_audit()"),
            main.index("readiness = raw_sidecar.launch()"),
        )
        admission = main[: main.index("readiness = raw_sidecar.launch()")]
        self.assertIn(
            "args.output.resolve(strict=False) == output",
            admission,
        )
        self.assertIn(
            "args.consumed_marker.resolve(strict=False) == consumed_marker",
            admission,
        )
        self.assertLess(
            main.index("run_root = run_parent /"),
            main.index("try:"),
        )
        self.assertLess(
            main.index("try:"),
            main.index("static = static_audit()", main.index("try:")),
        )

    def test_declared_closure_claim_does_not_smuggle_restoration(self):
        source = Path(candidate.__file__).read_text(encoding="utf-8")
        self.assertIn(
            '"restored_carrier_reuse_not_claimed": True',
            source,
        )
        self.assertIn("NOT_AVAILABLE_STATELESS_HTTP_LEASE", source)
        self.assertIn(
            "NOT_IMPLEMENTED_BY_CURRENT_SERVER_PROTOCOL",
            source,
        )
        self.assertNotIn(
            '"restoration_class": "EXACT_ALGEBRAIC_RESTORATION"',
            source,
        )

    def test_no_permanent_removal_api(self):
        source = Path(candidate.__file__).read_text(encoding="utf-8")
        runtime_source = source[: source.index("def static_audit()")]
        for token in ("rmtree", ".unlink(", "os.remove", "rmdir("):
            self.assertNotIn(token, runtime_source)


if __name__ == "__main__":
    unittest.main()
