"""Service layer for course-code driven paper discovery."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from xjtlu_downloader.core.download_service import DownloadService
from xjtlu_downloader.domain.models import DiscoveredViewerUrl, ETDAuthState
from xjtlu_downloader.infra.search_client import ETDAuthRequiredError, ETDSearchClient


class CourseDiscoveryService:
    """Discover viewer URLs from one or more course codes using the app session."""

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 60000,
        user_data_dir: Optional[Path] = None,
        search_client_factory: Callable[[ETDAuthState], ETDSearchClient] = ETDSearchClient,
    ):
        self.download_service = DownloadService(
            headless=headless,
            timeout=timeout,
            user_data_dir=user_data_dir,
        )
        self.search_client_factory = search_client_factory

    @staticmethod
    def normalize_course_codes(course_codes: list[str]) -> list[str]:
        """Upper-case and de-duplicate course codes while preserving order."""
        seen = set()
        normalized_codes = []

        for course_code in course_codes:
            normalized = course_code.strip().upper()
            if not normalized or normalized in seen:
                continue

            seen.add(normalized)
            normalized_codes.append(normalized)

        return normalized_codes

    def get_site_auth_state(self) -> ETDAuthState:
        """Return the current ETD site auth state stored in the browser profile."""
        return self.download_service.get_site_auth_state()

    def discover_viewer_urls(
        self,
        course_codes: list[str],
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> list[DiscoveredViewerUrl]:
        """Resolve every course code into a de-duplicated list of viewer URLs."""
        normalized_codes = self.normalize_course_codes(course_codes)
        if not normalized_codes:
            return []

        auth_state = self.get_site_auth_state()
        if not auth_state.is_authenticated:
            raise ETDAuthRequiredError(
                auth_state.error
                or "当前程序会话中没有检测到 ETD 网站登录信息。请先点击“登录 ETD”，并在 ETD 首页完成登录。"
            )

        client = self.search_client_factory(auth_state)
        discovered = []
        seen_record_ids = set()

        def update(message: str) -> None:
            if progress_callback:
                progress_callback(message)

        for course_code in normalized_codes:
            update(f"正在检索课程代码 {course_code} ...")
            course_items = client.discover_course_viewer_urls(course_code)
            update(f"课程 {course_code} 共发现 {len(course_items)} 条可下载记录。")

            for item in course_items:
                if item.record_id in seen_record_ids:
                    continue

                discovered.append(item)
                seen_record_ids.add(item.record_id)

        return discovered
