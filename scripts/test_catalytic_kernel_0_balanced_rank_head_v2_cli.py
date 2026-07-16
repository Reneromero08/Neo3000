#!/usr/bin/env python3
from __future__ import annotations

import unittest
from unittest import mock

import catalytic_kernel_0_balanced_rank_head_v2_cli as cli
import catalytic_kernel_0_balanced_rank_head_v2_entrypoint as entrypoint


class RankHeadV2CliBootstrapTests(unittest.TestCase):
    def test_bootstrap_delegates_to_canonical_entrypoint_module(self) -> None:
        with mock.patch.object(entrypoint, "main", return_value=0) as canonical_main:
            self.assertEqual(cli.main(), 0)
        canonical_main.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
