import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from xjtlu_downloader.domain.models import ETDAuthState
from xjtlu_downloader.ui.main_window import MainWindow


class MainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["test-main-window", "-platform", "offscreen"])

    def setUp(self):
        self.window = MainWindow()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()

    def test_add_urls_from_input_extracts_multiple_urls(self):
        self.window.url_input.setText(
            "https://etd.xjtlu.edu.cn/viewer.html?file=one https://etd.xjtlu.edu.cn/viewer.html?file=two"
        )

        self.window._add_urls_from_input()

        self.assertEqual(self.window.task_table.rowCount(), 2)
        self.assertEqual(
            self.window.task_table.item(0, 0).data(Qt.ItemDataRole.UserRole),
            "https://etd.xjtlu.edu.cn/viewer.html?file=one",
        )

    def test_add_urls_skips_duplicate_entries(self):
        first_url = "https://etd.xjtlu.edu.cn/viewer.html?file=one"
        second_url = "https://etd.xjtlu.edu.cn/viewer.html?file=two"

        added, skipped = self.window._add_urls([first_url, second_url, first_url])

        self.assertEqual((added, skipped), (2, 1))
        self.assertEqual(self.window.task_table.rowCount(), 2)

    def test_start_download_auto_adds_pending_input(self):
        self.window.url_input.setText("https://etd.xjtlu.edu.cn/viewer.html?file=pending")
        self.window.download_service.has_saved_session = lambda: False

        with patch.object(
            QMessageBox,
            "warning",
            return_value=QMessageBox.StandardButton.Ok,
        ):
            self.window._start_download()

        self.assertEqual(self.window.task_table.rowCount(), 1)
        self.assertEqual(
            self.window.task_table.item(0, 0).data(Qt.ItemDataRole.UserRole),
            "https://etd.xjtlu.edu.cn/viewer.html?file=pending",
        )

    def test_handle_task_started_preserves_viewer_url(self):
        viewer_url = "https://etd.xjtlu.edu.cn/viewer.html?file=abc"
        self.window._append_pending_url(viewer_url)
        self.window.total_tasks = 1

        self.window._handle_task_started(0, "sample.pdf", "C:/tmp/sample.pdf")

        item = self.window.task_table.item(0, 0)
        self.assertEqual(item.text(), "sample.pdf")
        self.assertEqual(item.data(Qt.ItemDataRole.UserRole), viewer_url)

    def test_refresh_session_status_shows_green_when_logged_in(self):
        self.window.download_service.get_site_auth_state = lambda: ETDAuthState(
            token="token",
            user_id="42",
            user_name="Kevin",
        )

        self.window._refresh_session_status()

        self.assertIn("已检测到有效的 ETD 登录状态", self.window.session_status_label.text())
        self.assertIn("无需再次点击", self.window.session_status_label.text())
        self.assertIn("#f0fdf4", self.window.session_status_label.styleSheet())
        self.assertEqual(self.window.login_button.text(), "重新登录 ETD")

    def test_refresh_session_status_shows_red_when_not_logged_in(self):
        self.window.download_service.get_site_auth_state = lambda: ETDAuthState()

        self.window._refresh_session_status()

        self.assertIn("尚未检测到有效的 ETD 登录状态", self.window.session_status_label.text())
        self.assertIn("#fef2f2", self.window.session_status_label.styleSheet())
        self.assertEqual(self.window.login_button.text(), "先登录 ETD")

    def test_start_course_discovery_from_input_extracts_codes(self):
        self.window.course_code_input.setText("eee205 CPT210")

        with patch.object(self.window, "_start_course_discovery") as start_discovery:
            self.window._start_course_discovery_from_input()

        start_discovery.assert_called_once_with(["EEE205", "CPT210"])

    def test_add_discovered_items_skips_duplicate_viewer_urls(self):
        self.window._append_pending_url("https://etd.xjtlu.edu.cn/viewer.html?file=one")

        added, skipped = self.window._add_discovered_items(
            [
                {
                    "course_code": "EEE205",
                    "paper_code": "EEE205",
                    "paper_title": "Digital Electronics II",
                    "year": "2024-2025",
                    "viewer_url": "https://etd.xjtlu.edu.cn/viewer.html?file=one",
                },
                {
                    "course_code": "CPT210",
                    "paper_code": "CPT210",
                    "paper_title": "Java Programming",
                    "year": "2024-2025",
                    "viewer_url": "https://etd.xjtlu.edu.cn/viewer.html?file=two",
                },
            ]
        )

        self.assertEqual((added, skipped), (1, 1))
        self.assertEqual(self.window.task_table.rowCount(), 2)
        self.assertEqual(
            self.window.task_table.item(1, 0).data(Qt.ItemDataRole.UserRole),
            "https://etd.xjtlu.edu.cn/viewer.html?file=two",
        )


if __name__ == "__main__":
    unittest.main()
