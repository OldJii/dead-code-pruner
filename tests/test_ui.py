import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

from pruner import ui
from pruner.ui import _display_width, _format_progress_line


class ProgressFormattingTest(unittest.TestCase):
    def test_progress_never_wraps_narrow_terminal(self):
        line = _format_progress_line(
            123, 1000, "Checking local unused-method refs",
            "42 referenced", indent=4, width=48)
        self.assertLessEqual(_display_width(line), 48)
        self.assertIn("12%", line)
        self.assertIn("123/1000", line)

    def test_progress_handles_wide_characters(self):
        line = _format_progress_line(
            50, 100, "正在检查本地引用", "10 个引用", indent=2, width=32)
        self.assertLessEqual(_display_width(line), 32)
        self.assertIn("50%", line)

    def test_same_stage_overwrites_and_next_stage_starts_new_line(self):
        output = io.StringIO()
        ui._progress_active = False
        ui._progress_key = None
        with patch.object(ui, '_IS_TTY', True), redirect_stdout(output):
            ui.progress(20, 100, 'Checking local unused-method refs')
            ui.progress(40, 100, 'Checking local unused-method refs')
            ui.progress(20, 100, 'Checking local promotion refs')
            ui.progress_done()
        rendered = output.getvalue()
        self.assertEqual(rendered.count('\n'), 2)
        self.assertEqual(rendered.count('\r\033[2K'), 3)

    def test_pipeline_hierarchy_is_phase_round_stage(self):
        output = io.StringIO()
        with redirect_stdout(output):
            ui.banner('Phase 3  Dead Declaration Cleanup')
            ui.round_header(2, 'Project convergence')
            ui.stage('Deleting definitions')
        rendered = output.getvalue()
        self.assertLess(rendered.index('Phase 3'), rendered.index('Round 2'))
        self.assertLess(rendered.index('Round 2'), rendered.index('Stage ·'))


if __name__ == '__main__':
    unittest.main()
