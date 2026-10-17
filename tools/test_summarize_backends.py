"""Failure explanations are based on recorded evidence, not fixture names."""
import unittest
from summarize_backends import failure_detail


class FailureDetailTests(unittest.TestCase):
    def test_software_explanation_requires_reshade_diagnostic(self):
        result = {'passed': False, 'error': 'ReShade/Phoenix control endpoint did not load'}
        self.assertIsNone(failure_detail(result))
        result['diagnostics'] = {'reshade_messages': [
            "Skipping device because the driver type is 'D3D_DRIVER_TYPE_WARP'."]}
        self.assertIn('software/reference', failure_detail(result))

    def test_helper_timeout_is_not_reported_as_unsupported(self):
        result = {'passed': False, 'error': 'No enhanced presentation within 20 render seconds',
                  'diagnostics': {'execution_mode': 'helper'}}
        self.assertIn('readiness deadline', failure_detail(result))
        self.assertNotIn('unsupported', failure_detail(result))

    def test_success_never_inherits_a_failure_explanation(self):
        self.assertIsNone(failure_detail({'passed': True, 'error':
            'This executable/API combination is not supported.'}))

    def test_install_rejection_does_not_imply_runtime_failure(self):
        self.assertIn('Installer', failure_detail({'passed': False, 'error':
            'Install failed: [Error] This executable/API combination is not supported.'}))


if __name__ == '__main__':
    unittest.main()
