import json
import os
from pathlib import Path
import unittest

from proofnav.validation import validate_runtime_trace


class LocalM0TraceIntegrationTests(unittest.TestCase):

    def test_local_m0_trace_when_explicitly_enabled(self):
        if os.environ.get("PROOFNAV_RUN_LOCAL_M0_INTEGRATION") != "1":
            self.skipTest("set PROOFNAV_RUN_LOCAL_M0_INTEGRATION=1 to opt in")
        configured = os.environ.get("PROOFNAV_M0_TRACE_PATH")
        if not configured:
            self.fail("PROOFNAV_M0_TRACE_PATH is required for the opt-in integration")
        path = Path(configured)
        self.assertTrue(path.is_file(), "configured M0 trace does not exist")
        with path.open(encoding="utf-8") as infile:
            events = [json.loads(line) for line in infile if line.strip()]
        validate_runtime_trace(events)
        self.assertGreater(len(events), 0)


if __name__ == "__main__":
    unittest.main()
