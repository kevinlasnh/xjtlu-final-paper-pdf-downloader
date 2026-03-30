"""Main PySide6 window for the desktop downloader."""

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from xjtlu_downloader.core.course_discovery_service import CourseDiscoveryService
from xjtlu_downloader.core.download_service import DownloadService
from xjtlu_downloader.core.input_parser import extract_course_codes, extract_urls_from_text


class DownloadWorker(QThread):
    """Background worker used by the desktop window."""

    task_started = Signal(int, str, str)
    task_progress = Signal(int, str)
    task_finished = Signal(int, dict)
    batch_finished = Signal(dict)

    def __init__(self, viewer_urls: list[str], output_dir: Path, headless: bool = True):
        super().__init__()
        self.viewer_urls = viewer_urls
        self.output_dir = output_dir
        self.headless = headless

    def run(self) -> None:
        service = DownloadService(headless=self.headless)
        success_count = 0
        fail_count = 0

        for index, viewer_url in enumerate(self.viewer_urls):
            try:
                prepared = service.prepare_download(viewer_url, self.output_dir)
                self.task_started.emit(index, prepared.filename, str(prepared.save_path))
                result = service.download_prepared(
                    prepared,
                    progress_callback=lambda message, idx=index: self.task_progress.emit(idx, message),
                )
                result_dict = result.to_legacy_dict()
            except Exception as exc:
                result_dict = {
                    "success": False,
                    "file_path": None,
                    "file_size": 0,
                    "error": str(exc),
                }

            if result_dict.get("success"):
                success_count += 1
            else:
                fail_count += 1

            self.task_finished.emit(index, result_dict)

        self.batch_finished.emit(
            {
                "success_count": success_count,
                "fail_count": fail_count,
                "total_count": len(self.viewer_urls),
            }
        )


class LoginWorker(QThread):
    """Background worker that opens the persistent login browser."""

    progress = Signal(str)
    finished = Signal(dict)

    def run(self) -> None:
        service = DownloadService(headless=False)
        result = service.open_login_browser(progress_callback=self.progress.emit)
        self.finished.emit(result.to_legacy_dict())


class CourseDiscoveryWorker(QThread):
    """Background worker that resolves course codes into viewer URLs."""

    progress = Signal(str)
    finished = Signal(dict)

    def __init__(self, course_codes: list[str]):
        super().__init__()
        self.course_codes = course_codes

    def run(self) -> None:
        service = CourseDiscoveryService(headless=True)
        try:
            items = service.discover_viewer_urls(self.course_codes, progress_callback=self.progress.emit)
            self.finished.emit(
                {
                    "success": True,
                    "items": [
                        {
                            "course_code": item.course_code,
                            "record_id": item.record_id,
                            "viewer_url": item.viewer_url,
                            "paper_code": item.paper_code,
                            "paper_title": item.paper_title,
                            "year": item.year,
                        }
                        for item in items
                    ],
                }
            )
        except Exception as exc:
            self.finished.emit({"success": False, "error": str(exc), "items": []})


class MainWindow(QMainWindow):
    """Minimal but structured PySide6 main window."""

    def __init__(self):
        super().__init__()
        self.download_service = DownloadService(headless=True)
        self.worker = None
        self.login_worker = None
        self.discovery_worker = None
        self.total_tasks = 0
        self.completed_tasks = 0
        self.setWindowTitle("XJTLU 期末试卷下载器")
        self.resize(920, 640)
        self._build_ui()
        self._refresh_session_status()

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("XJTLU 期末试卷下载器")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        subtitle = QLabel("推荐顺序：1. 登录 ETD  2. 通过两种方式之一把试卷加入下载队列  3. 再点击“开始下载队列”。")
        subtitle.setStyleSheet("color: #5f6b76;")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        session_row = QHBoxLayout()
        self.session_status_label = QLabel()
        self.session_status_label.setWordWrap(True)
        self.login_button = QPushButton("先登录 ETD")
        self.login_button.setStyleSheet(
            "background: #dc2626; color: white; font-weight: 700; padding: 6px 14px; border-radius: 6px;"
        )
        self.login_button.clicked.connect(self._start_login_flow)
        self.reset_session_button = QPushButton("重置会话")
        self.reset_session_button.clicked.connect(self._reset_session)
        session_row.addWidget(self.session_status_label, 1)
        session_row.addWidget(self.login_button)
        session_row.addWidget(self.reset_session_button)
        layout.addLayout(session_row)

        login_reminder = QLabel(
            "强提醒：请先点击上方“先登录 ETD”，并在程序浏览器中完成登录，再使用下面的任何下载功能。"
            "未登录时，课程代码模式无法正常发现试卷，viewer URL 下载也可能失败。"
        )
        self.login_reminder_label = login_reminder
        login_reminder.setWordWrap(True)
        login_reminder.setStyleSheet(
            "background: #fef2f2; color: #991b1b; border: 1px solid #fca5a5; border-radius: 6px; padding: 10px; font-weight: 600;"
        )
        layout.addWidget(login_reminder)

        queue_hint = QLabel(
            "添加到下载队列有两种方式：\n"
            "方式一：直接粘贴 PDF 查看器链接，适合一个文件一个文件添加。\n"
            "方式二：输入课程代码，适合按一门课批量发现并下载这门课的全部试卷。\n"
            "两种方式都会先把任务加入下面的下载队列；确认无误后，再点击“开始下载队列”。"
        )
        queue_hint.setWordWrap(True)
        queue_hint.setStyleSheet(
            "background: #f4f7fb; color: #334155; border: 1px solid #d8e1ec; border-radius: 6px; padding: 10px;"
        )
        layout.addWidget(queue_hint)

        url_label = QLabel("方式一：通过 PDF 查看器链接添加试卷")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("适合一个文件一个文件添加：先粘贴一条或多条 viewer URL，再加入下载队列。")
        self.url_input.setClearButtonEnabled(True)
        self.url_input.setToolTip(
            "适合逐个文件添加；支持直接回车加入下载队列。"
            "如果直接点“开始下载队列”，当前输入也会自动先入队。"
        )
        self.url_input.returnPressed.connect(self._add_urls_from_input)
        layout.addWidget(url_label)
        layout.addWidget(self.url_input)

        input_buttons = QHBoxLayout()
        self.add_url_button = QPushButton("加入下载队列")
        self.add_url_button.clicked.connect(self._add_urls_from_input)
        self.paste_button = QPushButton("粘贴并加入队列")
        self.paste_button.clicked.connect(self._add_urls_from_clipboard)
        self.remove_button = QPushButton("移除选中")
        self.remove_button.clicked.connect(self._remove_selected_rows)
        self.clear_button = QPushButton("清空队列")
        self.clear_button.clicked.connect(self._clear_task_table)
        input_buttons.addWidget(self.add_url_button)
        input_buttons.addWidget(self.paste_button)
        input_buttons.addWidget(self.remove_button)
        input_buttons.addWidget(self.clear_button)
        input_buttons.addStretch(1)
        layout.addLayout(input_buttons)

        course_code_label = QLabel("方式二：通过课程代码批量添加试卷")
        self.course_code_input = QLineEdit()
        self.course_code_input.setPlaceholderText(
            "适合按课程批量下载：输入一门或多门课程代码，例如 EEE205 CPT210 CAN202。"
        )
        self.course_code_input.setClearButtonEnabled(True)
        self.course_code_input.setToolTip(
            "适合一门课一门课地批量下载全部试卷；支持空格、换行或逗号分隔。"
            "会先发现试卷并加入下载队列，不会立刻开始下载。"
        )
        self.course_code_input.returnPressed.connect(self._start_course_discovery_from_input)
        layout.addWidget(course_code_label)
        layout.addWidget(self.course_code_input)

        course_buttons = QHBoxLayout()
        self.add_course_button = QPushButton("发现试卷并加入队列")
        self.add_course_button.clicked.connect(self._start_course_discovery_from_input)
        self.paste_course_button = QPushButton("粘贴课程代码并加入队列")
        self.paste_course_button.clicked.connect(self._start_course_discovery_from_clipboard)
        course_buttons.addWidget(self.add_course_button)
        course_buttons.addWidget(self.paste_course_button)
        course_buttons.addStretch(1)
        layout.addLayout(course_buttons)

        dir_row = QHBoxLayout()
        self.output_dir_input = QLineEdit(str((Path.cwd() / "downloads").resolve()))
        browse_button = QPushButton("选择目录")
        browse_button.clicked.connect(self._browse_output_dir)
        dir_row.addWidget(QLabel("保存目录"))
        dir_row.addWidget(self.output_dir_input, 1)
        dir_row.addWidget(browse_button)
        layout.addLayout(dir_row)

        button_row = QHBoxLayout()
        self.start_button = QPushButton("开始下载队列")
        self.start_button.clicked.connect(self._start_download)
        self.start_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.open_dir_button = QPushButton("打开目录")
        self.open_dir_button.clicked.connect(self._browse_output_dir)
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.open_dir_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("就绪。请先点击“先登录 ETD”，登录完成后再把试卷加入下载队列。")
        layout.addWidget(self.status_label)

        queue_label = QLabel("下载队列")
        queue_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(queue_label)

        self.task_table = QTableWidget(0, 4)
        self.task_table.setHorizontalHeaderLabels(["文件名", "状态", "目标路径", "备注"])
        self.task_table.horizontalHeader().setStretchLastSection(True)
        self.task_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.task_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.task_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self.task_table, 1)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("运行日志会显示在这里。")
        self.log_output.setMinimumHeight(160)
        layout.addWidget(self.log_output)

    def _refresh_session_status(self) -> None:
        profile_dir = self.download_service.get_session_profile_dir()
        auth_state = self.download_service.get_site_auth_state()

        if auth_state.is_authenticated:
            identity = auth_state.user_name or auth_state.user_id
            self.session_status_label.setText(
                f"登录状态：已检测到有效的 ETD 登录状态（{identity}）。\n"
                f"无需再次点击“先登录 ETD”，现在可以直接把试卷加入下载队列并开始下载。\n"
                f"会话目录：{profile_dir}"
            )
            self.session_status_label.setStyleSheet(
                "background: #f0fdf4; color: #166534; border: 1px solid #86efac; border-radius: 6px; padding: 10px; font-weight: 600;"
            )
            self.login_reminder_label.setText(
                "已检测到有效登录状态。你现在不需要再次点击“先登录 ETD”，"
                "可以直接通过 PDF 查看器链接或课程代码把试卷加入下载队列，然后开始下载。"
            )
            self.login_reminder_label.setStyleSheet(
                "background: #f0fdf4; color: #166534; border: 1px solid #86efac; border-radius: 6px; padding: 10px; font-weight: 600;"
            )
            self.login_button.setText("重新登录 ETD")
            self.login_button.setStyleSheet(
                "background: #15803d; color: white; font-weight: 700; padding: 6px 14px; border-radius: 6px;"
            )
        else:
            self.session_status_label.setText(
                f"登录状态：尚未检测到有效的 ETD 登录状态。\n"
                f"请先点击“先登录 ETD”，在程序浏览器的 ETD 首页完成登录。\n"
                f"会话目录：{profile_dir}"
            )
            self.session_status_label.setStyleSheet(
                "background: #fef2f2; color: #991b1b; border: 1px solid #fca5a5; border-radius: 6px; padding: 10px; font-weight: 600;"
            )
            self.login_reminder_label.setText(
                "强提醒：请先点击上方“先登录 ETD”，并在程序浏览器中完成登录，再使用下面的任何下载功能。"
                "未登录时，课程代码模式无法正常发现试卷，viewer URL 下载也可能失败。"
            )
            self.login_reminder_label.setStyleSheet(
                "background: #fef2f2; color: #991b1b; border: 1px solid #fca5a5; border-radius: 6px; padding: 10px; font-weight: 600;"
            )
            self.login_button.setText("先登录 ETD")
            self.login_button.setStyleSheet(
                "background: #dc2626; color: white; font-weight: 700; padding: 6px 14px; border-radius: 6px;"
            )

    def _set_busy_state(self, busy: bool) -> None:
        self.start_button.setEnabled(not busy)
        self.open_dir_button.setEnabled(not busy)
        self.login_button.setEnabled(not busy)
        self.reset_session_button.setEnabled(not busy)
        self.add_url_button.setEnabled(not busy)
        self.paste_button.setEnabled(not busy)
        self.remove_button.setEnabled(not busy)
        self.clear_button.setEnabled(not busy)
        self.url_input.setEnabled(not busy)
        self.add_course_button.setEnabled(not busy)
        self.paste_course_button.setEnabled(not busy)
        self.course_code_input.setEnabled(not busy)

    def _create_filename_item(self, label: str, viewer_url: str) -> QTableWidgetItem:
        item = QTableWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, viewer_url)
        return item

    def _iter_task_urls(self) -> list[str]:
        urls = []
        for row in range(self.task_table.rowCount()):
            item = self.task_table.item(row, 0)
            if not item:
                continue

            viewer_url = item.data(Qt.ItemDataRole.UserRole)
            if viewer_url:
                urls.append(viewer_url)

        return urls

    def _existing_task_urls(self) -> set[str]:
        return set(self._iter_task_urls())

    def _append_pending_task(self, viewer_url: str, label: str = "待解析", note: str = "") -> None:
        row = self.task_table.rowCount()
        self.task_table.insertRow(row)

        self.task_table.setItem(row, 0, self._create_filename_item(label, viewer_url))
        self.task_table.setItem(row, 1, QTableWidgetItem("待开始"))
        self.task_table.setItem(row, 2, QTableWidgetItem(""))
        self.task_table.setItem(row, 3, QTableWidgetItem(note or viewer_url))

    def _append_pending_url(self, viewer_url: str) -> None:
        self._append_pending_task(viewer_url)

    def _add_urls(self, urls: list[str]) -> tuple[int, int]:
        added = 0
        skipped = 0
        existing_urls = self._existing_task_urls()

        for viewer_url in urls:
            if viewer_url in existing_urls:
                skipped += 1
                continue

            self._append_pending_url(viewer_url)
            existing_urls.add(viewer_url)
            added += 1

        return added, skipped

    def _add_urls_from_input(self) -> None:
        raw_text = self.url_input.text().strip()
        if not raw_text:
            return

        urls = extract_urls_from_text(raw_text)
        if not urls and raw_text:
            urls = [raw_text]

        added, skipped = self._add_urls(urls)
        self.url_input.clear()
        if added:
            self._append_log(f"已将 {added} 条链接加入下载队列。现在可以点击“开始下载队列”。")
        if skipped:
            self._append_log(f"已跳过 {skipped} 条重复链接。")
        if not added and not skipped:
            QMessageBox.warning(self, "无法识别链接", "当前输入中没有识别到可用的 URL。")

    def _add_urls_from_clipboard(self) -> None:
        clipboard_text = QApplication.clipboard().text().strip()
        if not clipboard_text:
            QMessageBox.warning(self, "剪贴板为空", "剪贴板中没有可导入的内容。")
            return

        urls = extract_urls_from_text(clipboard_text)
        if not urls:
            QMessageBox.warning(self, "无法识别链接", "剪贴板中没有识别到可用的 URL。")
            return

        added, skipped = self._add_urls(urls)
        if added:
            self._append_log(f"已从剪贴板导入 {added} 条链接并加入下载队列。")
        if skipped:
            self._append_log(f"剪贴板中的 {skipped} 条重复链接已跳过。")

    def _add_discovered_items(self, items: list[dict]) -> tuple[int, int]:
        added = 0
        skipped = 0
        existing_urls = self._existing_task_urls()

        for item in items:
            viewer_url = (item.get("viewer_url") or "").strip()
            if not viewer_url:
                continue

            if viewer_url in existing_urls:
                skipped += 1
                continue

            paper_code = (item.get("paper_code") or "").strip()
            paper_title = (item.get("paper_title") or "").strip()
            course_code = (item.get("course_code") or "").strip()
            year = (item.get("year") or "").strip()

            label_parts = [part for part in (paper_code, paper_title) if part]
            note_parts = [part for part in (course_code, year) if part]

            label = " | ".join(label_parts) or course_code or "待解析"
            note = " / ".join(note_parts) or viewer_url

            self._append_pending_task(viewer_url, label=label, note=note)
            existing_urls.add(viewer_url)
            added += 1

        return added, skipped

    def _remove_selected_rows(self) -> None:
        selected_rows = sorted({index.row() for index in self.task_table.selectedIndexes()}, reverse=True)
        if not selected_rows:
            return

        for row in selected_rows:
            self.task_table.removeRow(row)

        self._append_log(f"已移除 {len(selected_rows)} 条待处理链接。")

    def _clear_task_table(self) -> None:
        if self.task_table.rowCount() == 0:
            return

        self.task_table.setRowCount(0)
        self._append_log("已清空下载队列。")

    def _browse_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择保存目录",
            self.output_dir_input.text() or str(Path.cwd()),
        )
        if directory:
            self.output_dir_input.setText(directory)

    def _append_log(self, message: str) -> None:
        self.log_output.appendPlainText(message)
        self.status_label.setText(message)

    def _start_course_discovery_from_input(self) -> None:
        raw_text = self.course_code_input.text().strip()
        if not raw_text:
            return

        course_codes = extract_course_codes(raw_text)
        self.course_code_input.clear()
        if not course_codes:
            QMessageBox.warning(self, "无法识别课程代码", "当前输入中没有识别到课程代码，例如 EEE205。")
            return

        self._start_course_discovery(course_codes)

    def _start_course_discovery_from_clipboard(self) -> None:
        clipboard_text = QApplication.clipboard().text().strip()
        if not clipboard_text:
            QMessageBox.warning(self, "剪贴板为空", "剪贴板中没有可导入的课程代码。")
            return

        course_codes = extract_course_codes(clipboard_text)
        if not course_codes:
            QMessageBox.warning(self, "无法识别课程代码", "剪贴板中没有识别到课程代码，例如 EEE205。")
            return

        self._start_course_discovery(course_codes)

    def _start_course_discovery(self, course_codes: list[str]) -> None:
        self._set_busy_state(True)
        self.progress_bar.show()
        self.progress_bar.setRange(0, 0)
        self._append_log(f"已启动课程代码发现任务：{', '.join(course_codes)}。发现完成后会自动加入下载队列。")

        self.discovery_worker = CourseDiscoveryWorker(course_codes)
        self.discovery_worker.progress.connect(self._append_log)
        self.discovery_worker.finished.connect(self._handle_course_discovery_finished)
        self.discovery_worker.start()

    def _start_login_flow(self) -> None:
        instructions = (
            "程序将打开一个独立的浏览器会话。\n\n"
            "请在打开的浏览器窗口中完成 ETD 首页登录，然后关闭整个浏览器窗口。"
            "课程代码模式会依赖该站点登录态。\n\n"
            "如果你只是想下载单条 viewer URL，也建议在首页登录一次后再继续。"
            "关闭后，程序会复用这份登录态进行下载。"
        )
        QMessageBox.information(self, "登录 ETD", instructions)
        self._append_log("准备打开程序登录浏览器。")
        self._set_busy_state(True)

        self.login_worker = LoginWorker()
        self.login_worker.progress.connect(self._handle_login_progress)
        self.login_worker.finished.connect(self._handle_login_finished)
        self.login_worker.start()

    def _handle_login_progress(self, message: str) -> None:
        self._append_log(message)

    def _handle_login_finished(self, result: dict) -> None:
        self._set_busy_state(False)
        self._refresh_session_status()

        message = result.get("message") or "登录流程已结束。"
        self._append_log(message)

        if result.get("success"):
            QMessageBox.information(self, "会话已更新", message)
        else:
            QMessageBox.warning(self, "登录流程结束", message)

    def _handle_course_discovery_finished(self, result: dict) -> None:
        self.progress_bar.hide()
        self._set_busy_state(False)

        if not result.get("success"):
            error = result.get("error") or "课程代码发现失败。"
            self._append_log(error)
            QMessageBox.warning(self, "课程代码发现失败", error)
            return

        items = result.get("items") or []
        added, skipped = self._add_discovered_items(items)
        self._append_log(
            f"课程代码发现结束。新增 {added} 条，跳过重复 {skipped} 条。"
            "如果队列内容无误，现在可以点击“开始下载队列”。"
        )

        if added == 0:
            QMessageBox.information(
                self,
                "课程代码发现完成",
                "没有新增可加入下载队列的试卷记录。可能是没有结果，或这些记录已经在列表中。",
            )
        else:
            QMessageBox.information(
                self,
                "课程代码发现完成",
                f"已将 {added} 条试卷加入下载队列。确认无误后，请点击“开始下载队列”。",
            )

    def _reset_session(self) -> None:
        answer = QMessageBox.question(
            self,
            "重置会话",
            "这会删除程序保存的 ETD 登录会话。确定继续吗？",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self.download_service.clear_session()
        self._refresh_session_status()
        self._append_log("已重置程序登录会话。")
        QMessageBox.information(self, "会话已重置", "程序登录会话已清除。下次下载前请重新点击“登录 ETD”。")

    def _start_download(self) -> None:
        if self.url_input.text().strip():
            self._add_urls_from_input()

        urls = self._iter_task_urls()

        if not urls:
            QMessageBox.warning(
                self,
                "下载队列为空",
                "请先用 PDF 查看器链接或课程代码，把至少一个任务加入下载队列，然后再点击“开始下载队列”。",
            )
            return

        if not self.download_service.has_saved_session():
            QMessageBox.warning(
                self,
                "缺少登录会话",
                "尚未检测到程序登录会话。\n请先点击“登录 ETD”，在程序浏览器中完成登录后再下载。",
            )
            return

        output_dir = Path(self.output_dir_input.text().strip()).expanduser()
        self.total_tasks = len(urls)
        self.completed_tasks = 0

        for index in range(len(urls)):
            filename_item = self.task_table.item(index, 0)
            if filename_item:
                viewer_url = filename_item.data(Qt.ItemDataRole.UserRole)
            else:
                viewer_url = ""
                filename_item = self._create_filename_item("待解析", viewer_url)

            self.task_table.setItem(index, 0, filename_item)
            self.task_table.setItem(index, 1, QTableWidgetItem("排队中"))
            self.task_table.setItem(index, 2, QTableWidgetItem(str(output_dir)))
            self.task_table.setItem(index, 3, QTableWidgetItem("等待处理"))

        self._set_busy_state(True)
        self.progress_bar.show()
        self.progress_bar.setRange(0, self.total_tasks)
        self.progress_bar.setValue(0)
        self._append_log("已启动下载队列。")

        self.worker = DownloadWorker(urls, output_dir, headless=True)
        self.worker.task_started.connect(self._handle_task_started)
        self.worker.task_progress.connect(self._handle_task_progress)
        self.worker.task_finished.connect(self._handle_task_finished)
        self.worker.batch_finished.connect(self._handle_batch_finished)
        self.worker.start()

    def _handle_task_started(self, row: int, filename: str, save_path: str) -> None:
        existing_item = self.task_table.item(row, 0)
        viewer_url = existing_item.data(Qt.ItemDataRole.UserRole) if existing_item else ""
        self.task_table.setItem(row, 0, self._create_filename_item(filename, viewer_url))
        self.task_table.setItem(row, 1, QTableWidgetItem("运行中"))
        self.task_table.setItem(row, 2, QTableWidgetItem(save_path))
        self.task_table.setItem(row, 3, QTableWidgetItem("浏览器任务已启动"))
        self._append_log(f"[{row + 1}/{self.total_tasks}] 开始处理 {filename}")

    def _handle_task_progress(self, row: int, message: str) -> None:
        self.task_table.setItem(row, 1, QTableWidgetItem("运行中"))
        self.task_table.setItem(row, 3, QTableWidgetItem(message))
        self._append_log(f"[{row + 1}/{self.total_tasks}] {message}")

    def _handle_task_finished(self, row: int, result: dict) -> None:
        self.completed_tasks += 1
        self.progress_bar.setValue(self.completed_tasks)
        if result.get("success"):
            self.task_table.setItem(row, 1, QTableWidgetItem("成功"))
            self.task_table.setItem(row, 2, QTableWidgetItem(result.get("file_path") or ""))
            self.task_table.setItem(row, 3, QTableWidgetItem("下载完成"))
            self._append_log(f"[{row + 1}/{self.total_tasks}] 下载完成。")
            return

        error = result.get("error") or "未知错误"
        self.task_table.setItem(row, 1, QTableWidgetItem("失败"))
        self.task_table.setItem(row, 3, QTableWidgetItem(error))
        self._append_log(f"[{row + 1}/{self.total_tasks}] 下载失败：{error}")

    def _handle_batch_finished(self, summary: dict) -> None:
        self.progress_bar.hide()
        self._set_busy_state(False)
        self._refresh_session_status()
        message = (
            f"批量任务结束。成功 {summary['success_count']} 个，"
            f"失败 {summary['fail_count']} 个，共 {summary['total_count']} 个。"
        )
        self._append_log(message)

        if summary["fail_count"]:
            QMessageBox.warning(self, "批量下载完成", message)
        else:
            QMessageBox.information(self, "批量下载完成", message)
