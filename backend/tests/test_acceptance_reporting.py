"""The acceptance sweep's failure-aggregation contract.

The sweep must run EVERY independent product assertion and then exit non-zero,
not abort on the first failure — an earlier `check()` called `sys.exit(1)`
immediately, so one missing event hid every later assertion. Setup failures are
different and must still abort at once with exit code 2.

These tests import the sweep module with its URL constants patched, so no server is
needed and nothing is executed against the network.
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SWEEP = os.path.join(BACKEND, "tests", "acceptance_sweep.py")
PY = sys.executable


def load_sweep():
    spec = importlib.util.spec_from_file_location("acceptance_sweep_probe", SWEEP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class CheckAggregationTests(unittest.TestCase):

    def setUp(self):
        self.mod = load_sweep()
        self.mod._FAILURES.clear()
        self.mod._CHECKS[0] = 0

    def test_check_does_not_exit_on_failure(self):
        """check() must RECORD a failure and keep going, not terminate."""
        result = self.mod.check(False, "a failing assertion")
        self.assertFalse(result)
        self.assertEqual(self.mod._FAILURES, ["a failing assertion"],
                         "failure was not recorded")
        # Reaching this line at all proves it did not sys.exit().

    def test_check_collects_multiple_failures(self):
        """Every independent assertion must be evaluated, not just the first."""
        for i in range(4):
            self.mod.check(False, f"failure {i}")
        self.mod.check(True, "a passing assertion")
        self.assertEqual(len(self.mod._FAILURES), 4)
        self.assertEqual(self.mod._CHECKS[0], 5,
                         "not all assertions were evaluated")

    def test_check_returns_truthiness_of_condition(self):
        self.assertTrue(self.mod.check(True, "ok"))
        self.assertFalse(self.mod.check(False, "bad"))
        self.assertFalse(self.mod.check(0, "zero is falsy"))
        self.assertTrue(self.mod.check(1, "one is truthy"))

    def test_saved_source_has_no_exit_inside_check(self):
        """Guard the regression at the source level: sys.exit(1) must not creep
        back into check(), and must not sit before the append."""
        src = open(SWEEP, encoding="utf-8").read()
        start = src.index("def check(")
        end = src.index("def fatal(")
        body = src[start:end]
        self.assertNotIn("sys.exit", body,
                         "check() must not terminate the run")


class ExitCodeContractTests(unittest.TestCase):
    """The three exit codes must be distinguishable, proven by running the module."""

    def _run(self, snippet):
        script = (
            "import importlib.util, sys, os\n"
            f"spec = importlib.util.spec_from_file_location('sw', r'{SWEEP}')\n"
            "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
            + snippet
        )
        return subprocess.run([PY, "-c", script], capture_output=True, text=True,
                              timeout=60)

    def test_product_failure_exits_1(self):
        p = self._run("m._FAILURES.clear(); m._CHECKS[0]=0\n"
                      "m.check(False, 'x')\n"
                      "print('FAILED'); sys.exit(1 if m._FAILURES else 0)\n")
        self.assertEqual(p.returncode, 1, f"expected exit 1, got {p.returncode}")

    def test_all_pass_exits_0(self):
        p = self._run("m._FAILURES.clear(); m._CHECKS[0]=0\n"
                      "m.check(True, 'x')\n"
                      "print('ALL PASS'); sys.exit(1 if m._FAILURES else 0)\n")
        self.assertEqual(p.returncode, 0, f"expected exit 0, got {p.returncode}")

    def test_fatal_exits_2(self):
        p = self._run("m.fatal('wrong server')\n")
        self.assertEqual(p.returncode, 2,
                         f"setup failure must exit 2, got {p.returncode}")
        self.assertIn("SETUP FAILURE", p.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
