from __future__ import annotations

import ast
import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import catalytic_runner
from result_schema import SpecValidationError


class CatalyticRunnerTests(unittest.TestCase):
    def load(self, name: str):
        return catalytic_runner.load_spec(
            SCRIPTS / "experiment_specs" / name
        )

    def test_0101_historical_calibration_spec_validates(self):
        receipt = catalytic_runner.validate_spec(
            self.load("neo-exp-0101-calibration.json")
        )
        self.assertTrue(receipt["valid"])
        self.assertEqual(receipt["callback_count"], 48)
        self.assertEqual(receipt["direct_action_count"], 29)
        self.assertFalse(receipt["model_contact_allowed"])

    def test_0102_precontact_calibration_spec_validates(self):
        receipt = catalytic_runner.validate_spec(
            self.load("neo-exp-0102-precontact-calibration.json")
        )
        self.assertTrue(receipt["valid"])
        self.assertEqual(receipt["callback_count"], 16)
        self.assertEqual(receipt["direct_action_count"], 28)
        self.assertFalse(receipt["model_contact_allowed"])

    def test_model_contact_cannot_be_enabled(self):
        spec = copy.deepcopy(
            self.load("neo-exp-0102-precontact-calibration.json")
        )
        spec["model_contact_allowed"] = True
        with self.assertRaisesRegex(
            SpecValidationError,
            "forbid model contact",
        ):
            catalytic_runner.validate_spec(spec)

    def test_restoration_scope_cannot_be_qualified_away(self):
        spec = copy.deepcopy(
            self.load("neo-exp-0101-calibration.json")
        )
        del spec["restoration_scope"]["cuda_kv"]
        with self.assertRaisesRegex(
            SpecValidationError,
            "restoration_scope must name",
        ):
            catalytic_runner.validate_spec(spec)

    def test_schedule_totals_are_executed_as_data(self):
        spec = copy.deepcopy(
            self.load("neo-exp-0102-precontact-calibration.json")
        )
        spec["callback_schedule"][0]["count"] = 2
        with self.assertRaisesRegex(
            SpecValidationError,
            "callback_schedule total 17 != 16",
        ):
            catalytic_runner.validate_spec(spec)

    def test_active_runner_imports_no_legacy_wrapper(self):
        tree = ast.parse(
            Path(catalytic_runner.__file__).read_text(encoding="utf-8")
        )
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        for prefix in catalytic_runner.LEGACY_CONTROLLER_PREFIXES:
            self.assertNotIn(prefix, imported)
            self.assertNotIn(prefix, sys.modules)

    def test_specs_are_plain_immutable_data_not_python_imports(self):
        for path in sorted(
            (SCRIPTS / "experiment_specs").glob("*.json")
        ):
            value = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(value["legacy_controller_status"], "RETIRED_NOT_IMPORTED")


if __name__ == "__main__":
    unittest.main()
