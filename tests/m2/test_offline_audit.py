import ast
import copy
from pathlib import Path
import unittest

from proofnav.offline import OracleOfflineVerifier, ReplayTerminalController
from proofnav.runtime import CertificateBuilder, TerminalController
from tests.m2.fixtures import controlled_state, execution, scenario


class OfflineAuditTests(unittest.TestCase):

    def test_offline_outcome_taxonomy_and_no_runtime_feedback(self):
        bundle = scenario()
        state = controlled_state(bundle)
        certificate = CertificateBuilder().build(state, "FOUND")["certificate"]
        accepted = ReplayTerminalController().decide(
            state, "FOUND", certificate, execution(),
        )
        before = copy.deepcopy(accepted)
        verifier = OracleOfflineVerifier()
        true_accept = verifier.verify(bundle["truth"], accepted, certificate)
        self.assertEqual(true_accept["outcome"], "TRUE_ACCEPT")
        self.assertEqual(accepted, before)
        self.assertIsNone(true_accept["feedback_to_runtime"])

        wrong_scope_certificate = copy.deepcopy(certificate)
        wrong_scope_certificate["scope_contract_id"] = "another-scope"
        wrong_scope = verifier.verify(
            bundle["truth"], accepted, wrong_scope_certificate,
        )
        self.assertEqual(wrong_scope["outcome"], "WRONG_SCOPE")
        self.assertEqual(wrong_scope["audit_disposition"], "UNRESOLVED")

        production_reject = TerminalController().decide(
            state, "FOUND", certificate, execution(),
        )
        self.assertEqual(production_reject["online_verification"]["status"], "REJECT")
        false_reject = verifier.verify(bundle["truth"], production_reject, certificate)
        self.assertEqual(false_reject["outcome"], "FALSE_REJECT")
        self.assertTrue(false_reject["online_offline_conflict"])

        empty_state = controlled_state(bundle, evidence=[])
        unresolved_terminal = ReplayTerminalController().decide(
            empty_state, "FOUND", None, execution(max_step=True),
        )
        unresolved = verifier.verify(bundle["truth"], unresolved_terminal, None)
        self.assertEqual(unresolved["outcome"], "UNRESOLVED")

    def test_offline_verifier_has_no_online_verifier_dependency(self):
        path = Path(__file__).resolve().parents[2] / "proofnav" / "offline" / "oracle_verifier.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        self.assertFalse([name for name in imports if name.startswith("proofnav.runtime")])


if __name__ == "__main__":
    unittest.main()
