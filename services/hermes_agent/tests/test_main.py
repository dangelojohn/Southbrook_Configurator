# SPDX-License-Identifier: LGPL-3.0-only
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hermes_agent import main as main_module


class TestHermesAgentMain(unittest.TestCase):

    @patch.object(main_module, "run_passive_service")
    @patch.object(main_module, "load_config")
    def test_serve_command_runs_passive_service(self, load_config, run_service):
        cfg = object()
        load_config.return_value = cfg

        result = main_module.main(["serve"])

        self.assertEqual(result, 0)
        run_service.assert_called_once_with(cfg)

    @patch.object(main_module, "load_config")
    def test_check_command_validates_configuration(self, load_config):
        cfg = object()
        load_config.return_value = cfg

        result = main_module.main(["check"])

        self.assertEqual(result, 0)
        load_config.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
